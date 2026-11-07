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
    from app.db import engine, utcnow
    from app.services.alerts import run_saved_searches
    import re, sqlalchemy as sa
    from app.models import alert_sent, saved_search, tender
    with engine.begin() as c:
        c.execute(sa.delete(alert_sent))
        c.execute(sa.update(saved_search).values(last_run_at=None, max_items=3))
        first = run_saved_searches(c, force=True)
        sent1 = set(c.execute(sa.select(alert_sent.c.ocid)).scalars())
        again = run_saved_searches(c)  # no forzado: aún no toca (frecuencia diaria)
        second = run_saved_searches(c, force=True)
        rows = c.execute(sa.select(alert_sent.c.ocid)).scalars().all()
        st = dict(c.execute(sa.select(tender.c.ocid, tender.c.status_details).where(tender.c.ocid.in_(rows))).all())
        dl = dict(c.execute(sa.select(tender.c.ocid, tender.c.deadline_at).where(tender.c.ocid.in_(rows))).all())
    assert first["mails"] >= 1 and 1 <= first["tenders"] <= 3 * first["mails"]
    assert again["mails"] == 0
    assert len(rows) == len(set(rows)), "un concurso no se repite en la misma semana"
    assert sent1 <= set(rows) and second["tenders"] == len(rows) - len(sent1)
    now = utcnow()
    assert all(st[o] == "Vigente" and (dl[o] is None or dl[o] >= now) for o in rows)
    mail = sorted(Path(settings.outbox_dir).glob("*.html"))[-1].read_text()
    link = re.search(r'href="([^"]*links/feedback[^"]*)"', mail).group(1).replace("&amp;", "&")
    r = client.get(link.replace(settings.public_api_url, ""))
    assert r.status_code == 200 and "Gracias" in r.text
    assert "inválido" in client.get("/api/v1/links/feedback?t=bad").text


def _search(client, filters, **kw):
    r = client.post("/api/v1/tenders/search", json={"q": "", "filters": filters, "limit": 100, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_hard_filters_include_exclude(client):
    facets = client.get("/api/v1/catalogs/facets").json()
    for k in ("category", "status_details", "department", "entity_type", "method"):
        assert facets[k], k
    total = _search(client, {})["total"]
    for key in ("category", "status_details", "entity_type", "method", "department"):
        v = facets[key][0]["value"]
        inc = _search(client, {key: {"op": "in", "values": [v]}})["total"]
        exc = _search(client, {key: {"op": "out", "values": [v]}})["total"]
        assert inc == facets[key][0]["count"] and inc + exc == total, key
    goods = _search(client, {"category": {"op": "in", "values": ["goods"]}})["items"]
    assert goods and all(i["category"] == "goods" for i in goods)
    no_goods = _search(client, {"category": {"op": "out", "values": ["goods"]}})["items"]
    assert all(i["category"] != "goods" for i in no_goods)
    et = facets["entity_type"][0]["value"]
    assert all(i["entity_type"] == et for i in _search(client, {"entity_type": {"op": "in", "values": [et]}})["items"])
    # entidad compradora por texto
    buyer = _search(client, {})["items"][0]["buyer_name"]
    word = buyer.split()[-1]
    inc = _search(client, {"buyer": {"op": "in", "values": [word]}})
    assert inc["total"] and all(word.lower() in i["buyer_name"].lower() for i in inc["items"])
    exc = _search(client, {"buyer": {"op": "out", "values": [word]}})
    assert inc["total"] + exc["total"] == total
    # proveedor adjudicado
    aw = _search(client, {"awarded_only": True})["items"]
    tender = client.get(f"/api/v1/tenders/{aw[0]['nog']}").json()
    sid = tender["awards"][0]["supplier_id"]
    inc = _search(client, {"supplier": {"op": "in", "values": [sid]}})
    assert inc["total"] >= 1 and all(i["status"] == "complete" for i in inc["items"])
    exc = _search(client, {"supplier": {"op": "out", "values": [sid]}})
    assert inc["total"] + exc["total"] == total
    # fechas y disponibilidad
    assert _search(client, {"date_preset": "7d"})["total"] <= _search(client, {"date_preset": "1y"})["total"]
    assert _search(client, {"date_from": "2100-01-01"})["total"] == 0
    assert all(i["is_open"] for i in _search(client, {"open_only": True})["items"])
    # formato anterior sigue funcionando
    assert _search(client, {"status": "open"})["total"] == _search(client, {"status_details": {"op": "in", "values": ["Vigente"]}})["total"]


def test_filters_in_views(client):
    import json
    from urllib.parse import quote
    q = lambda f: quote(json.dumps(f))  # noqa: E731
    base = client.get("/api/v1/dashboard").json()
    none = client.get(f"/api/v1/dashboard?f={q({'date_from': '2100-01-01'})}").json()
    assert base["kpis"]["open"] > 0 and none["kpis"]["open"] == 0 and none["filtered"] and not none["recommended"]
    recs = client.get("/api/v1/recommendations").json()["items"]
    cat = recs[0]["category"]
    only = client.get(f"/api/v1/recommendations?f={q({'category': {'op': 'in', 'values': [cat]}})}").json()["items"]
    out = client.get(f"/api/v1/recommendations?f={q({'category': {'op': 'out', 'values': [cat]}})}").json()["items"]
    assert only and all(i["category"] == cat for i in only)
    assert all(i["category"] != cat for i in out)
    o = client.get(f"/api/v1/opportunities?f={q({'date_from': '2100-01-01'})}").json()
    assert o["opportunities"] == []
    assert client.get(f"/api/v1/opportunities?f={q({'category': {'op': 'out', 'values': ['works']}})}").status_code == 200


def test_saved_combination_preview_and_limits(client):
    body = {"name": "Bienes vigentes", "filters": {"category": {"op": "in", "values": ["goods"]}}, "max_items": 4}
    s = client.post("/api/v1/saved-searches", json=body).json()
    assert s["max_items"] == 4
    p = client.get(f"/api/v1/saved-searches/{s['id']}/preview").json()
    assert p["total"] > 0 and 1 <= len(p["items"]) <= 4
    assert all(i["category"] == "goods" and i["is_open"] for i in p["items"])
    assert client.post("/api/v1/saved-searches", json={**body, "max_items": 11}).status_code == 400
    assert client.post("/api/v1/saved-searches", json={**body, "max_items": 0}).status_code == 400
    client.delete(f"/api/v1/saved-searches/{s['id']}")


def test_admin_status(client):
    s = client.get("/api/v1/admin/status").json()
    assert s["tenders"] > 0 and s["without_embedding"] == 0


def test_nit_crud_and_history(client):
    base = client.get("/api/v1/org/suppliers").json()["items"]
    assert base, "la cuenta demo trae un NIT"
    demo = base[0]
    # agregar (normaliza guiones y prefijo) y validar
    assert client.post("/api/v1/org/suppliers", json={"nit": "123-456-7", "label": ""}).status_code == 400
    assert client.post("/api/v1/org/suppliers", json={"nit": "12A45", "label": "X"}).status_code == 400
    items = client.post("/api/v1/org/suppliers", json={"nit": "123-456-7", "label": "Sucursal"}).json()["items"]
    assert any(i["id"] == "GT-NIT-1234567" and i["label"] == "Sucursal" and not i["found"] for i in items)
    assert client.post("/api/v1/org/suppliers", json={"nit": "GT-NIT-1234567", "label": "Otra"}).status_code == 409
    # editar NIT y nombre
    items = client.put("/api/v1/org/suppliers/1234567", json={"nit": "7654321K", "label": "Sucursal 2"}).json()["items"]
    assert any(i["id"] == "GT-NIT-7654321K" and i["label"] == "Sucursal 2" for i in items)
    assert client.put("/api/v1/org/suppliers/999", json={"nit": "1", "label": "x"}).status_code == 404
    assert client.put("/api/v1/org/suppliers/7654321K", json={"nit": demo["nit"], "label": "x"}).status_code == 409
    client.put(f"/api/v1/org/suppliers/{demo['nit']}", json={"nit": demo["nit"], "label": "Principal"})
    # historial
    h = client.get("/api/v1/org/history").json()
    assert h["has_data"]
    t = h["totals"]
    assert t["participated"] == t["won"] + t["lost"] + t["in_progress"] + t["void"]
    assert t["won"] > 0 and 0 <= t["win_rate"] <= 1
    assert {n["id"] for n in h["by_nit"]} == {demo["id"], "GT-NIT-7654321K"}
    main = next(n for n in h["by_nit"] if n["id"] == demo["id"])
    assert main["label"] == "Principal" and main["won"] == t["won"]
    assert len(h["recent"]["won"]) == min(t["won"], 50) and all(i["nog"] for i in h["recent"]["won"])
    assert sum(m["participated"] for m in h["monthly"]) == t["participated"]
    # eliminar
    items = client.delete("/api/v1/org/suppliers/7654321K").json()["items"]
    assert [i["id"] for i in items] == [demo["id"]]
    assert client.get("/api/v1/auth/me").json()["supplier_ids"] == [demo["id"]]


def test_change_email(client):
    me = client.get("/api/v1/auth/me").json()
    assert client.put("/api/v1/auth/email", json={"email": "nuevo@empresa.gt", "password": "mala"}).status_code == 403
    assert client.put("/api/v1/auth/email", json={"email": "no-es-correo", "password": "demo1234"}).status_code == 400
    r = client.put("/api/v1/auth/email", json={"email": " Nuevo@Empresa.gt ", "password": "demo1234"})
    assert r.status_code == 200 and r.json()["email"] == "nuevo@empresa.gt"
    assert client.get("/api/v1/auth/me").json()["email"] == "nuevo@empresa.gt"
    client.put("/api/v1/auth/email", json={"email": me["email"], "password": "demo1234"})
