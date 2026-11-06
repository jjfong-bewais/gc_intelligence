import json
import zipfile
from datetime import datetime

import sqlalchemy as sa


def test_zip_ingest_roundtrip(seeded, tmp_path):
    """Un ZIP con la estructura real (records[].compiledRelease) se carga y es idempotente."""
    from app.db import engine
    from app.demo.generator import generate
    from app.ingest.client import iter_zip_records
    from app.ingest.loader import load_records
    from app.models import tender

    recs = generate(now=datetime(2026, 3, 1), seed=7, n_historical=20, n_open=5)
    p = tmp_path / "2026-03.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("2026-03.json", json.dumps({"version": "1.1", "records": recs}))
    s1 = load_records(iter_zip_records(p))
    assert s1.inserted + s1.updated + s1.skipped >= 1 and s1.invalid == 0
    n = engine.connect().execute(sa.select(sa.func.count()).select_from(tender)).scalar()
    s2 = load_records(iter_zip_records(p))
    assert s2.inserted == 0 and s2.updated == 0
    assert engine.connect().execute(sa.select(sa.func.count()).select_from(tender)).scalar() == n


def test_parser_unit_price_only_single_item():
    from app.ingest.parser import parse_dt
    assert parse_dt("2026-03-01T10:00:00-06:00").hour == 16
    assert parse_dt(None) is None and parse_dt("basura") is None
