import os
from pathlib import Path


def test_requires_auth(seeded):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/dashboard").status_code == 401
        assert c.post("/api/v1/auth/login", json={"email": "x@y.z", "password": "bad"}).status_code == 401


def test_search_modes(client):
    first = client.post("/api/v1/tenders/search", json={"q": "", "filters": {"status": "open"}}).json()["items"][0]
    q = " ".join(first["title"].split()[:3])
    for mode in ("keyword", "semantic", "hybrid"):
        r = client.post("/api/v1/tenders/search", json={"q": q, "mode": mode, "filters": {"status": "open"}})
        assert r.status_code == 200 and r.json()["total"] > 0, mode
        assert all(i["is_open"] for i in r.json()["items"])
    r = client.post("/api/v1/tenders/search", json={"q": "", "filters": {"status": "awarded"}, "limit": 5})
    assert len(r.json()["items"]) == 5


def test_detail_and_comparables(client):
    it = client.post("/api/v1/tenders/search", json={"q": "papel bond", "filters": {"status": "open"}}).json()["items"][0]
    d = client.get(f"/api/v1/tenders/{it['nog']}").json()
    assert d["items"]
    c = client.get(f"/api/v1/tenders/{it['nog']}/price-comparables").json()
    assert c["items"][0]["stats"]["n"] > 0
    assert client.get("/api/v1/tenders/1/similar").status_code == 404


def test_favorites_feedback_changes_recs(client):
    recs = client.get("/api/v1/recommendations").json()["items"]
    assert recs
    target = recs[0]["ocid"]
    assert client.put(f"/api/v1/favorites/{target}", json={"status": "cotizado"}).status_code == 200
    assert client.put(f"/api/v1/feedback/{target}", json={"signal": -1}).status_code == 200
    again = [r["ocid"] for r in client.get("/api/v1/recommendations").json()["items"]]
    assert target not in again
    favs = client.get("/api/v1/favorites").json()["items"]
    assert favs[0]["favorite"] == "cotizado"
    client.delete(f"/api/v1/favorites/{target}")
    client.put(f"/api/v1/feedback/{target}", json={"signal": 0})


def test_opportunities_and_inventory(client):
    o = client.get("/api/v1/opportunities").json()
    assert o["opportunities"] and o["peers"]
    m = client.get("/api/v1/inventory/matches").json()["items"]
    assert m and m[0]["matches"]


def test_inventory_import(client):
    csv = "SKU;Producto;Unidad\nA1;Resma papel bond carta;resma\n"
    r = client.post("/api/v1/inventory/import", files={"file": ("i.csv", csv.encode(), "text/csv")})
    assert r.json()["imported"] == 1
    bad = client.post("/api/v1/inventory/import", files={"file": ("i.csv", b"a,b\n1,2\n", "text/csv")})
    assert bad.status_code == 400
    demo = (Path(__file__).parents[1] / "app/demo/inventario_demo.csv").read_bytes()
    assert client.post("/api/v1/inventory/import", files={"file": ("i.csv", demo, "text/csv")}).json()["imported"] == 8


def test_saved_search_alert_flow(client):
    s = client.post("/api/v1/saved-searches", json={"name": "t", "q": "toner impresora", "filters": {"status": "open"}}).json()
    assert client.get(f"/api/v1/saved-searches/{s['id']}/preview").json()["total"] > 0
    assert client.put(f"/api/v1/saved-searches/{s['id']}", json={"name": "t2", "q": "toner", "frequency": "weekly"}).json()["name"] == "t2"
    assert client.delete(f"/api/v1/saved-searches/{s['id']}").status_code == 200


def test_alert_emails_and_links(client):
    from app.config import settings
    from app.db import engine
    from app.services.alerts import run_saved_searches
    import re, sqlalchemy as sa
    from app.models import saved_search
    with engine.begin() as c:
        c.execute(sa.update(saved_search).values(last_run_at=None))
        first = run_saved_searches(c, force=True)
        second = run_saved_searches(c, force=True)
    assert first["mails"] >= 1 and second["mails"] == 0  # idempotente
    mail = sorted(Path(settings.outbox_dir).glob("*.html"))[-1].read_text()
    link = re.search(r'href="([^"]*links/feedback[^"]*)"', mail).group(1).replace("&amp;", "&")
    r = client.get(link.replace(settings.public_api_url, ""))
    assert r.status_code == 200 and "Gracias" in r.text
    assert "inválido" in client.get("/api/v1/links/feedback?t=bad").text


def test_admin_status(client):
    s = client.get("/api/v1/admin/status").json()
    assert s["tenders"] > 0 and s["without_embedding"] == 0
