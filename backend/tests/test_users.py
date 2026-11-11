"""Roles, permisos y administración de usuarios."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

API = "/api/v1"
PUBLIC = {f"{API}/health", f"{API}/auth/login", f"{API}/auth/logout", f"{API}/links/{{kind}}"}


def _outbox_password(email: str) -> str:
    """Clave temporal del último correo enviado a `email` (MAIL_PROVIDER=file en las pruebas)."""
    box = Path(__import__("os").environ["OUTBOX_DIR"])
    files = sorted(f for f in box.glob("*.html") if f"to: {email}" in f.read_text(encoding="utf-8")[:200])
    return re.search(r"<code[^>]*>(.*?)</code>", files[-1].read_text(encoding="utf-8")).group(1)


@pytest.fixture()
def new_member(client):
    """Crea un member desde el admin y devuelve (id, email, clave_temporal)."""
    email = f"m{len(client.get(API + '/users').json()['items'])}@prueba.gt"
    r = client.post(f"{API}/users", json={"email": email, "name": "Prueba", "company": "Prueba S.A."})
    assert r.status_code == 200 and r.json()["email_sent"]
    yield r.json()["user"]["id"], email, _outbox_password(email)
    client.delete(f"{API}/users/{r.json()['user']['id']}")


def login(email, password) -> TestClient:
    from app.main import app
    c = TestClient(app)
    r = c.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return c


def test_every_route_requires_login(seeded):
    from app.main import app
    c = TestClient(app)
    checked = 0
    for path, methods in app.openapi()["paths"].items():
        if path in PUBLIC:
            continue
        url = re.sub(r"\{[^}]+\}", "1", path)
        for method in methods:
            assert c.request(method.upper(), url).status_code == 401, f"{method} {path} no exige sesión"
            checked += 1
    assert checked > 40


def test_signup_is_gone(client):
    assert client.post(f"{API}/auth/register", json={"email": "a@b.co", "password": "12345678"}).status_code in (404, 405)


def test_invite_forces_password_change(client, new_member):
    uid, email, temp = new_member
    u = login(email, temp)
    me = u.get(f"{API}/auth/me").json()
    assert me["must_change_password"] and me["role"] == "member"
    assert u.get(f"{API}/dashboard").status_code == 403  # bloqueado hasta cambiar la clave
    assert u.put(f"{API}/auth/password", json={"current_password": "mala", "new_password": "NuevaClave123"}).status_code == 403
    assert u.put(f"{API}/auth/password", json={"current_password": temp, "new_password": "corta"}).status_code == 400
    assert u.put(f"{API}/auth/password", json={"current_password": temp, "new_password": temp}).status_code == 400
    assert u.put(f"{API}/auth/password", json={"current_password": temp, "new_password": "NuevaClave123"}).status_code == 200
    assert u.get(f"{API}/dashboard").status_code == 200
    assert login(email, "NuevaClave123")


def test_member_has_whole_platform_but_no_admin(client, new_member):
    uid, email, temp = new_member
    u = login(email, temp)
    u.put(f"{API}/auth/password", json={"current_password": temp, "new_password": "NuevaClave123"})
    assert "admin" not in u.get(f"{API}/auth/me").json()["permissions"]
    for ok in ("/inventory", "/favorites", "/saved-searches", "/suppliers?q=a", "/opportunities", "/recommendations"):
        assert u.get(API + ok).status_code == 200, ok
    for denied in ("/users", "/admin/status"):
        assert u.get(API + denied).status_code == 403, denied
    assert u.post(f"{API}/users", json={"email": "x@y.gt"}).status_code == 403
    assert u.post(f"{API}/admin/embed").status_code == 403


def test_create_validation(client, new_member):
    _, email, _ = new_member
    assert client.post(f"{API}/users", json={"email": email}).status_code == 409
    assert client.post(f"{API}/users", json={"email": "no-es-correo"}).status_code == 400
    assert client.post(f"{API}/users", json={"email": "z@z.gt", "role": "root"}).status_code == 400


def test_admin_cannot_lock_itself_out(client):
    me = client.get(f"{API}/auth/me").json()
    assert client.delete(f"{API}/users/{me['id']}").status_code == 409
    assert client.patch(f"{API}/users/{me['id']}", json={"role": "member"}).status_code == 409
    assert client.patch(f"{API}/users/{me['id']}", json={"active": False}).status_code == 409
    assert client.patch(f"{API}/users/{me['id']}", json={"name": "Usuario Demo"}).status_code == 200


def test_deactivate_and_reactivate(client, new_member):
    uid, email, temp = new_member
    u = login(email, temp)
    u.put(f"{API}/auth/password", json={"current_password": temp, "new_password": "NuevaClave123"})
    assert client.patch(f"{API}/users/{uid}", json={"active": False}).status_code == 200
    assert u.get(f"{API}/auth/me").status_code == 401  # la sesión abierta deja de valer
    r = TestClient(__import__("app.main", fromlist=["app"]).app).post(f"{API}/auth/login", json={"email": email, "password": "NuevaClave123"})
    assert r.status_code == 403
    client.patch(f"{API}/users/{uid}", json={"active": True})
    assert login(email, "NuevaClave123")


def test_permission_overrides(client, new_member):
    uid, email, temp = new_member
    u = login(email, temp)
    u.put(f"{API}/auth/password", json={"current_password": temp, "new_password": "NuevaClave123"})
    assert client.patch(f"{API}/users/{uid}", json={"perm_overrides": {"deny": ["inventory"]}}).status_code == 200
    assert u.get(f"{API}/inventory").status_code == 403
    assert u.get(f"{API}/favorites").status_code == 200
    assert "inventory" not in u.get(f"{API}/auth/me").json()["permissions"]
    # el permiso de administrador no se puede dar por excepción
    assert client.patch(f"{API}/users/{uid}", json={"perm_overrides": {"grant": ["admin"]}}).status_code == 400
    client.patch(f"{API}/users/{uid}", json={"perm_overrides": {"deny": []}})
    assert u.get(f"{API}/inventory").status_code == 200


def test_reset_password(client, new_member):
    uid, email, temp = new_member
    u = login(email, temp)
    u.put(f"{API}/auth/password", json={"current_password": temp, "new_password": "NuevaClave123"})
    assert client.post(f"{API}/users/{uid}/reset-password").json()["email_sent"]
    t2 = _outbox_password(email)
    assert t2 != temp
    assert login(email, t2).get(f"{API}/auth/me").json()["must_change_password"]


def test_delete_removes_everything(client):
    from app.db import engine
    from app.models import app_user, org_supplier, organization
    import sqlalchemy as sa
    r = client.post(f"{API}/users", json={"email": "borrar@prueba.gt", "company": "Borrar"}).json()["user"]
    temp = _outbox_password("borrar@prueba.gt")
    u = login("borrar@prueba.gt", temp)
    u.put(f"{API}/auth/password", json={"current_password": temp, "new_password": "NuevaClave123"})
    assert u.post(f"{API}/org/suppliers", json={"nit": "999111", "label": "x"}).status_code == 200
    assert client.delete(f"{API}/users/{r['id']}").status_code == 200
    with engine.connect() as c:
        assert not c.execute(sa.select(app_user).where(app_user.c.id == r["id"])).first()
        assert not c.execute(sa.select(organization).where(organization.c.name == "Borrar")).first()
        assert not c.execute(sa.select(org_supplier).where(org_supplier.c.supplier_id == "GT-NIT-999111")).first()
    assert client.delete(f"{API}/users/{r['id']}").status_code == 404


def test_inactive_users_get_no_alerts(client, new_member):
    from app.db import engine
    from app.services.alerts import run_saved_searches
    uid, email, temp = new_member
    u = login(email, temp)
    u.put(f"{API}/auth/password", json={"current_password": temp, "new_password": "NuevaClave123"})
    body = {"name": "todo", "q": "papel", "mode": "hybrid", "filters": {}, "frequency": "daily", "active": True, "max_items": 5}
    assert u.post(f"{API}/saved-searches", json=body).status_code == 200
    with engine.begin() as c:
        assert run_saved_searches(c, force=True, user_id=uid)["mails"] == 1
    client.patch(f"{API}/users/{uid}", json={"active": False})
    with engine.begin() as c:
        assert run_saved_searches(c, force=True, user_id=uid)["mails"] == 0
