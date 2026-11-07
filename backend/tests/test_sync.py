import json
import zipfile
from pathlib import Path


class FakeClient:
    """Sustituye al cliente HTTP: 3 años de archivos; cada ZIP lleva un concurso mínimo."""
    def list_files(self, year):
        return [{"year": year, "month": m, "timestamp": f"{year}-{m}", "files": {"json": f"u/{year}/{m}"}}
                for m in range(1, 13)]

    def download(self, url, dest_dir=None):
        from app.demo.generator import generate
        from datetime import datetime
        _, y, m = url.split("/")
        recs = generate(now=datetime(int(y), int(m), 15), seed=int(y) * 100 + int(m), n_historical=1, n_open=0)[:1]
        p = Path(dest_dir) / f"{y}-{m}.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("f.json", json.dumps({"records": recs}))
        return p


def test_sync_since_walks_years(seeded, monkeypatch):
    from app.ingest import sync as S
    monkeypatch.setattr(S, "GuatecomprasClient", FakeClient)
    monkeypatch.setattr(S, "load_records", lambda recs, known: S.LoadStats())
    out = S.sync(months_back=0, since="2024-11", log=lambda *_: None)
    keys = sorted(out)
    assert keys[0] == "2024-11" and "2024-10" not in keys
    assert keys[-1] == "2026-12" and "2025-06" in keys
    # months_back > 0 toma los últimos N de todo el rango, no solo del último año
    out2 = S.sync(months_back=3, since="2024-11", force=True, log=lambda *_: None)
    assert sorted(out2) == ["2026-10", "2026-11", "2026-12"]
    # un año explícito conserva el comportamiento anterior
    out3 = S.sync(year=2025, months_back=2, force=True, log=lambda *_: None)
    assert sorted(out3) == ["2025-11", "2025-12"]
