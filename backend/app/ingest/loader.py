"""Carga idempotente de registros OCDS en la base (upsert por lotes)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import time

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..db import engine, utcnow
from ..models import (award, bid, contract, document, party, price_obs, tender, tender_item)
from .parser import parse_release

CHUNK = 300
# Columnas que nunca se sobrescriben al actualizar (las gestionan otros procesos).
TENDER_KEEP = {"ocid", "first_seen_at", "embedding", "emb_hash", "emb_sig"}
ITEM_KEEP = {"id", "embedding", "emb_hash", "emb_sig"}


@dataclass
class LoadStats:
    seen: int = 0
    skipped: int = 0
    inserted: int = 0
    updated: int = 0
    invalid: int = 0


def _upsert(conn: sa.Connection, table: sa.Table, rows: list[dict], pk: list[str], keep: set[str]) -> None:
    if not rows:
        return
    ins = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
    stmt = ins(table)
    cols = [c for c in rows[0] if c not in keep and c not in pk]
    stmt = stmt.on_conflict_do_update(index_elements=pk, set_={c: stmt.excluded[c] for c in cols})
    conn.execute(stmt, rows)


def known_release_dates() -> dict[str, str]:
    with engine.connect() as conn:
        return {r[0]: r[1] for r in conn.execute(sa.select(tender.c.ocid, tender.c.release_date))}


def load_records(records: Iterable[dict], known: dict[str, str] | None = None) -> LoadStats:
    """records: iterable de {ocid, compiledRelease|release}. Omite los que no cambiaron."""
    known = known if known is not None else known_release_dates()
    stats = LoadStats()
    buf: list[dict] = []
    for rec in records:
        stats.seen += 1
        rel = rec.get("compiledRelease") or rec
        if known.get(rel.get("ocid")) == rel.get("date") and rel.get("date"):
            stats.skipped += 1
            continue
        parsed = parse_release(rel)
        if not parsed:
            stats.invalid += 1
            continue
        parsed["_new"] = rel.get("ocid") not in known
        buf.append(parsed)
        if len(buf) >= CHUNK:
            _flush(buf, stats)
            buf = []
    if buf:
        _flush(buf, stats)
    return stats


def _flush(buf: list[dict], stats: LoadStats) -> None:
    """Un lote por transacción; reintenta si Postgres cancela por deadlock o corte de conexión."""
    for attempt in range(5):
        try:
            return _flush_once(buf, stats)
        except sa.exc.OperationalError:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))


def _flush_once(buf: list[dict], stats: LoadStats) -> None:
    now = utcnow()
    ocids = [p["tender"]["ocid"] for p in buf]
    parties: dict[str, dict] = {}
    for p in buf:
        for pt in p["parties"]:
            parties[pt["id"]] = pt
    tenders = [{**p["tender"], "updated_at": now, "first_seen_at": now} for p in buf]
    items = [i for p in buf for i in p["items"]]
    new_item_ids = {i["id"] for i in items}

    with engine.begin() as conn:
        _upsert(conn, party, list(parties.values()), ["id"], set())
        _upsert(conn, tender, tenders, ["ocid"], TENDER_KEEP)
        # ítems: upsert (conserva vectores) y borrado de los que ya no existen
        existing = conn.execute(
            sa.select(tender_item.c.id).where(tender_item.c.ocid.in_(ocids))
        ).scalars().all()
        stale = [i for i in existing if i not in new_item_ids]
        for s in range(0, len(stale), 500):
            conn.execute(sa.delete(tender_item).where(tender_item.c.id.in_(stale[s:s + 500])))
        _upsert(conn, tender_item, items, ["id"], ITEM_KEEP)
        # tablas sin vectores: reemplazo completo por concurso
        for table, key in ((bid, "bids"), (award, "awards"), (contract, "contracts"),
                           (document, "docs"), (price_obs, "prices")):
            conn.execute(sa.delete(table).where(table.c.ocid.in_(ocids)))
            rows = [r for p in buf for r in p[key]]
            if rows:
                conn.execute(sa.insert(table), rows)
    for p in buf:
        if p["_new"]:
            stats.inserted += 1
        else:
            stats.updated += 1
