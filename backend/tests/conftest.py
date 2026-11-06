import os
import tempfile

# La base de pruebas se fija antes de importar la app. TEST_DATABASE_URL permite probar en Postgres.
_tmp = tempfile.mkdtemp(prefix="gc_test_")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["GC_MODE"] = "demo"
os.environ["MAIL_PROVIDER"] = "file"
os.environ["OUTBOX_DIR"] = f"{_tmp}/outbox"
os.environ["EMBEDDINGS_PROVIDER"] = "local"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def seeded():
    from app.demo.seed import seed_demo
    seed_demo(n_historical=250, n_open=40, reset=True, log=lambda *_: None)


@pytest.fixture(scope="session")
def client(seeded):
    from app.main import app
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"email": "demo@gcintelligence.local", "password": "demo1234"})
        assert r.status_code == 200
        yield c
