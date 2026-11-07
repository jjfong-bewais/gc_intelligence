"""Diagnóstico: ¿el OCDS real de Guatecompras trae fecha de cierre? ¿Llega a la base?

Uso (desde backend/, con el venv activo):
    python ../scripts/diag_deadline.py                 # descarga el mes actual y analiza
    python ../scripts/diag_deadline.py --zip ruta.zip  # usa un ZIP ya descargado
    DATABASE_URL=postgresql://... python ../scripts/diag_deadline.py --db   # revisa la base
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def walk(obj, prefix=""):
    """Rutas de hojas cuyo nombre sugiere fecha/periodo."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v, prefix + "[]")
    else:
        low = prefix.lower()
        if any(w in low for w in ("date", "period", "deadline", "cierre", "fecha")):
            yield prefix, obj


def analyze_zip(path: str, limit: int) -> None:
    from app.ingest.client import iter_zip_records
    from app.ingest.parser import parse_dt

    n = vig = 0
    status = Counter()
    paths_all, paths_vig, samples = Counter(), Counter(), {}
    tp_keys = Counter()
    end_raw = end_parsed = 0
    for rec in iter_zip_records(path):
        rel = rec.get("compiledRelease") or rec
        t = rel.get("tender") or {}
        n += 1
        sd = t.get("statusDetails")
        status[repr(sd)] += 1
        tp = t.get("tenderPeriod")
        tp_keys[tuple(sorted(tp.keys())) if isinstance(tp, dict) else repr(type(tp).__name__)] += 1
        ed = (tp or {}).get("endDate") if isinstance(tp, dict) else None
        if ed:
            end_raw += 1
            if parse_dt(ed):
                end_parsed += 1
            else:
                samples.setdefault("UNPARSEABLE endDate", ed)
        seen = set(p for p, _ in walk(t, "tender"))
        paths_all.update(seen)
        if sd == "Vigente":
            vig += 1
            paths_vig.update(seen)
            for p, v in walk(t, "tender"):
                samples.setdefault(p, v)
        if limit and n >= limit:
            break

    print(f"\nRegistros: {n}   Vigentes: {vig}")
    print("\nstatusDetails:", dict(status.most_common(15)))
    print("\nForma de tender.tenderPeriod:", dict(tp_keys.most_common(10)))
    print(f"\ntenderPeriod.endDate presente: {end_raw}/{n}   parseable por parse_dt: {end_parsed}")
    print("\nCampos de fecha/periodo en tender (todos | vigentes) y ejemplo:")
    for p, c in paths_all.most_common():
        print(f"  {p:60s} {c:7d} | {paths_vig.get(p, 0):6d}   {str(samples.get(p, ''))[:40]}")
    if "UNPARSEABLE endDate" in samples:
        print("\nEjemplo de endDate que parse_dt rechaza:", samples["UNPARSEABLE endDate"])


def analyze_db() -> None:
    import sqlalchemy as sa
    from app.db import engine
    q = """
      select status_details, count(*) n, count(deadline_at) con_cierre,
             min(deadline_at) min_cierre, max(deadline_at) max_cierre
      from tender group by 1 order by 2 desc limit 15"""
    with engine.connect() as c:
        for r in c.execute(sa.text(q)):
            print(dict(r._mapping))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip")
    ap.add_argument("--db", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="máx. registros a leer (0 = todos)")
    a = ap.parse_args()
    if a.db:
        analyze_db()
        sys.exit()
    path = a.zip
    if not path:
        from app.ingest.client import GuatecomprasClient
        cl = GuatecomprasClient()
        files = [f for f in cl.list_files(date.today().year) if f["month"] == date.today().month]
        print("Descargando", files[-1]["files"]["json"], "...")
        path = str(cl.download(files[-1]["files"]["json"]))
    analyze_zip(path, a.limit)
