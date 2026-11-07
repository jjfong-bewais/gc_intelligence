"""Sincronización con Guatecompras: archivos mensuales del año configurado."""
from __future__ import annotations

import shutil
import tempfile
from datetime import datetime

import sqlalchemy as sa

from ..config import settings
from ..db import engine, utcnow
from ..models import ingest_file
from .client import GuatecomprasClient, iter_zip_records
from .loader import LoadStats, known_release_dates, load_records


def select_files(files: list[dict], months_back: int, only: list[str] | None) -> list[dict]:
    if only:
        wanted = set(only)
        return [f for f in files if f"{f['year']}-{f['month']:02d}" in wanted]
    return files[-months_back:] if months_back > 0 else files


def _ym(s: str) -> tuple[int, int]:
    y, m = s.strip().split("-")[:2]
    return int(y), int(m)


def sync(
    year: int | None = None, months_back: int = 2, only: list[str] | None = None,
    force: bool = False, since: str | None = None, log=print,
) -> dict[str, LoadStats]:
    """Descarga y procesa los últimos `months_back` meses (0 = todos) desde `since`.

    Sin `year`, recorre desde `since` (por defecto DATA_FROM, p. ej. 2024-01) hasta el año
    actual; con `year`, solo ese año.

    Una adjudicación tardía reescribe el archivo del mes de la convocatoria, por eso
    por defecto se revisan los dos últimos archivos disponibles. Un archivo se omite si
    su `timestamp` no cambió desde la última corrida; y dentro de un archivo se omiten
    los registros cuya fecha de release no cambió.
    """
    client = GuatecomprasClient()
    if year:
        listed = client.list_files(year)
    else:
        start = _ym(since or settings.data_from)
        listed = []
        for y in range(start[0], utcnow().year + 1):
            listed += [f for f in client.list_files(y) if (f["year"], f["month"]) >= start]
    files = select_files(listed, months_back, only)
    with engine.connect() as conn:
        done = {r[0]: r[1] for r in conn.execute(sa.select(ingest_file.c.key, ingest_file.c.file_timestamp))}
    known = known_release_dates()
    results: dict[str, LoadStats] = {}
    tmp = tempfile.mkdtemp(prefix="gc_sync_")
    try:
        for f in files:
            key = f"{f['year']}-{f['month']:02d}"
            if not force and done.get(key) == f.get("timestamp"):
                log(f"{key}: sin cambios, se omite")
                continue
            t0 = datetime.now()
            log(f"{key}: descargando {f['files']['json']}")
            path = client.download(f["files"]["json"], tmp)
            stats = load_records(iter_zip_records(path), known)
            path.unlink(missing_ok=True)
            _mark(key, f.get("timestamp"), stats)
            results[key] = stats
            log(
                f"{key}: {stats.seen} registros, {stats.inserted} nuevos, {stats.updated} "
                f"actualizados, {stats.skipped} sin cambios, {stats.invalid} inválidos "
                f"({(datetime.now() - t0).seconds}s)"
            )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return results


def _mark(key: str, ts: str | None, stats: LoadStats) -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    with engine.begin() as conn:
        ins = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
        stmt = ins(ingest_file).values(
            key=key, file_timestamp=ts, n_records=stats.seen,
            n_changed=stats.inserted + stats.updated, processed_at=utcnow(),
        )
        conn.execute(stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={c: stmt.excluded[c] for c in ("file_timestamp", "n_records", "n_changed", "processed_at")},
        ))
