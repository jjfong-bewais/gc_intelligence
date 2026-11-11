"""Métricas de uso: captura (middleware, telemetría, sesiones), permisos y cálculo de KPIs."""
from datetime import timedelta

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from tests.test_users import API, login, new_member  # noqa: F401  (new_member es una fixture)

ADMIN = {"email": "demo@gcintelligence.local", "password": "demo1234"}


@pytest.fixture()
def clean():
    """Vacía las tablas de uso antes de cada prueba."""
    from app.db import engine
    from app.models import usage_event, usage_session
    from app.services import usage
    usage.flush()
    usage._SESS.clear()
    with engine.begin() as c:
        c.execute(sa.delete(usage_event))
        c.execute(sa.delete(usage_session))
    yield


def _rows(table):
    from app.db import engine
    from app.services import usage
    assert usage.flush()
    with engine.begin() as c:
        return [dict(r) for r in c.execute(sa.select(table)).mappings()]


def _member(new_member):
    uid, email, temp = new_member
    c = login(email, temp)
    c.put(f"{API}/auth/password", json={"current_password": temp, "new_password": "NuevaClave123"})
    return uid, c


def test_classify_and_normalize():
    from app.services import usage
    assert usage.classify("POST", "/tenders/search") == ("search", "search")
    assert usage.classify("GET", "/tenders/{nog}") == ("tender_detail", "view")
    assert usage.classify("GET", "/tenders/{nog}/similar") == ("tender_detail", "similar")
    assert usage.classify("PUT", "/favorites/{ocid}") == ("favorites", "save")
    assert usage.classify("GET", "/health") is None and usage.classify("GET", "/auth/me") is None
    assert usage.classify("GET", "/admin/metrics/overview") is None
    assert usage.page_feature("/tenders/:id") == "tender_detail" and usage.page_feature("/") == "dashboard"
    assert usage.normalize_path("/tenders/123456?x=1") == "/tenders/:id"


def test_member_actions_are_recorded_with_search_text(client, new_member, clean):
    from app.models import usage_event, usage_session
    uid, c = _member(new_member)
    r = c.post(f"{API}/tenders/search", json={"q": "papel bond carta", "mode": "keyword", "filters": {"status": "open", "x": []}})
    assert r.status_code == 200
    c.get(f"{API}/auth/me")  # no se registra
    ev = [e for e in _rows(usage_event) if e["user_id"] == uid]
    s = [e for e in ev if e["feature"] == "search"]
    assert len(s) == 1 and s[0]["action"] == "search" and s[0]["status"] == 200 and s[0]["duration_ms"] is not None
    assert s[0]["props"]["q"] == "papel bond carta" and s[0]["props"]["mode"] == "keyword"
    assert s[0]["props"]["filters"] == {"status": "open"} and s[0]["props"]["total"] >= 0
    assert not [e for e in ev if e["route"] == "/auth/me"]
    sessions = [x for x in _rows(usage_session) if x["user_id"] == uid]
    assert len(sessions) == 1 and sessions[0]["n_events"] >= 1


def test_login_events(client, new_member, clean):
    from app.models import usage_event
    uid, email, temp = new_member
    from app.main import app
    c = TestClient(app)
    assert c.post(f"{API}/auth/login", json={"email": email, "password": "mala"}).status_code == 401
    assert c.post(f"{API}/auth/login", json={"email": email, "password": temp}).status_code == 200
    acts = [e["action"] for e in _rows(usage_event) if e["feature"] == "auth"]
    assert acts == ["login_failed", "login"]


def test_telemetry_page_views_and_active_time(client, new_member, clean):
    from app.models import usage_event, usage_session
    uid, c = _member(new_member)
    body = {"events": [{"type": "page_view", "path": "/tenders/998877", "src": "alert"},
                       {"type": "page_view", "path": "/search"},
                       {"type": "heartbeat", "seconds": 30}, {"type": "heartbeat", "seconds": 30}]}
    assert c.post(f"{API}/telemetry", json=body).status_code == 200
    pages = [e for e in _rows(usage_event) if e["user_id"] == uid and e["kind"] == "page"]
    assert [(p["feature"], p["route"]) for p in pages] == [("tender_detail", "/tenders/:id"), ("search", "/search")]
    s = [x for x in _rows(usage_session) if x["user_id"] == uid][0]
    assert s["active_seconds"] == 60 and s["n_pages"] == 2 and s["entry_source"] == "alert"


def test_telemetry_validation_and_auth(client):
    from app.main import app
    assert TestClient(app).post(f"{API}/telemetry", json={"events": []}).status_code == 401
    assert client.post(f"{API}/telemetry", json={"events": [{"type": "bogus"}]}).status_code == 422
    assert client.post(f"{API}/telemetry", json={"events": [{"type": "heartbeat"}] * 51}).status_code == 422


def test_session_splits_after_30_minutes(client, new_member, clean):
    from app.db import utcnow
    from app.models import usage_session
    from app.services import usage
    uid, _ = new_member[0], None
    t0 = utcnow() - timedelta(hours=3)
    ev = lambda ts: {"kind": "api", "ts": ts, "user_id": uid, "feature": "search", "action": "search", "route": "/x", "status": 200}  # noqa: E731
    usage.write_batch([ev(t0), ev(t0 + timedelta(minutes=10)), ev(t0 + timedelta(minutes=50))])
    ses = sorted(_rows(usage_session), key=lambda s: s["started_at"])
    ses = [s for s in ses if s["user_id"] == uid]
    assert len(ses) == 2 and ses[0]["n_events"] == 2 and ses[1]["n_events"] == 1


def test_metrics_require_admin(client, new_member):
    uid, c = _member(new_member)
    for path in ("overview", "users", "features", "searches", "retention", "health"):
        assert c.get(f"{API}/admin/metrics/{path}").status_code == 403, path
    assert c.get(f"{API}/admin/metrics/users/{uid}").status_code == 403
    for path in ("overview", "users", "features", "searches", "retention", "health"):
        assert client.get(f"{API}/admin/metrics/{path}").status_code == 200, path
    assert client.get(f"{API}/admin/metrics/overview?days=500").status_code == 422  # máx. 90


def test_kpis_from_activity(client, new_member, clean):
    uid, c = _member(new_member)
    c.post(f"{API}/tenders/search", json={"q": "papel", "mode": "keyword"})
    c.post(f"{API}/tenders/search", json={"q": "papel", "mode": "keyword"})
    c.post(f"{API}/tenders/search", json={"q": "zzzqqqxxx inexistente", "mode": "keyword"})
    c.post(f"{API}/telemetry", json={"events": [{"type": "page_view", "path": "/search"}, {"type": "heartbeat", "seconds": 45}]})
    from app.services import usage
    usage.flush()

    ov = client.get(f"{API}/admin/metrics/overview?days=7").json()
    k = ov["kpis"]
    assert k["active_users"] == 1 and k["sessions"] == 1 and k["dau"] == 1 and k["events"] >= 4
    assert k["active_median_s"] == 45 and len(ov["series"]) == 7 and sum(map(sum, ov["heatmap"])) == 1

    users = client.get(f"{API}/admin/metrics/users?days=7").json()["items"]
    me = next(u for u in users if u["id"] == uid)
    assert me["searches"] == 3 and me["score"] >= 3 and me["status"] == "active" and me["sessions"] == 1
    assert all(u["role"] != "admin" for u in users)  # administradores excluidos por defecto
    with_admins = client.get(f"{API}/admin/metrics/users?days=7&exclude_admins=false").json()["items"]
    assert any(u["role"] == "admin" for u in with_admins)

    se = client.get(f"{API}/admin/metrics/searches?days=7").json()
    assert se["kpis"]["searches"] == 3 and se["top_terms"][0]["term"] == "papel" and se["top_terms"][0]["count"] == 2
    assert se["modes"] == {"keyword": 3} and se["kpis"]["zero_result_rate"] is not None
    assert se["recent"][0]["q"]  # el texto completo de la búsqueda queda visible para el admin

    ft = client.get(f"{API}/admin/metrics/features?days=7").json()
    search = next(f for f in ft["items"] if f["feature"] == "search")
    assert search["visits"] == 1 and search["users"] == 1 and search["adoption"] == 1.0
    assert ft["funnel"][1]["count"] == 1  # una sesión buscó
    assert "Inventario" in ft["unused"]

    det = client.get(f"{API}/admin/metrics/users/{uid}?days=7").json()
    assert det["user"]["id"] == uid and det["sessions"] and det["events"] and det["features"]
    assert client.get(f"{API}/admin/metrics/users/999999").status_code == 404

    h = client.get(f"{API}/admin/metrics/health?days=7").json()
    assert h["kpis"]["requests"] >= 3 and any(i["route"] == "/tenders/search" for i in h["items"])
    rt = client.get(f"{API}/admin/metrics/retention").json()
    assert rt["cohorts"] and rt["cohorts"][-1]["retention"][0] == 1.0


def test_admin_activity_not_counted_by_default(client, clean):
    client.post(f"{API}/tenders/search", json={"q": "algo", "mode": "keyword"})
    from app.services import usage
    usage.flush()
    assert client.get(f"{API}/admin/metrics/overview?days=7").json()["kpis"]["sessions"] == 0
    assert client.get(f"{API}/admin/metrics/overview?days=7&exclude_admins=false").json()["kpis"]["sessions"] == 1
    # y consultar el panel no genera eventos propios
    from app.models import usage_event
    assert not [e for e in _rows(usage_event) if e["route"].startswith("/admin")]


def test_prune_removes_old_rows(client, new_member, clean):
    from app.db import engine, utcnow
    from app.services import usage
    uid = new_member[0]
    old = utcnow() - timedelta(days=120)
    usage.write_batch([{"kind": "api", "ts": old, "user_id": uid, "feature": "search", "action": "search", "route": "/x", "status": 200},
                       {"kind": "api", "ts": utcnow(), "user_id": uid, "feature": "search", "action": "search", "route": "/x", "status": 200}])
    with engine.begin() as c:
        out = usage.prune(c, 90)
    assert out == {"events": 1, "sessions": 1}
