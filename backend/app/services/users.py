"""Gestión de cuentas: alta con clave temporal, edición, desactivación y baja.

Cada usuario es su propia «organización» (un registro `organization` creado junto con él, que
guarda el nombre de la empresa); los NIT, el inventario y las alertas cuelgan de ella.
Solo se usa desde el router de administración y la línea de comandos.
"""
from __future__ import annotations

import re
import secrets

import sqlalchemy as sa

from ..config import settings
from ..models import (alert_delivery, alert_sent, app_user, favorite, feedback, inventory_alert, inventory_item,
                      org_supplier, organization, saved_search)
from ..permissions import ROLES, normalize_overrides
from ..security import hash_password
from .mailer import send_email

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


class UserError(Exception):
    """Error de regla de negocio; main.py lo convierte en una respuesta HTTP."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 200:
        raise UserError("Escribe un correo válido")
    return email


def check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise UserError(f"La contraseña necesita al menos {MIN_PASSWORD} caracteres")


def check_role(role: str) -> str:
    if role not in ROLES:
        raise UserError(f"Rol inválido (usa: {', '.join(ROLES)})")
    return role


def temp_password() -> str:
    return secrets.token_urlsafe(9)


def _email_taken(conn: sa.Connection, email: str, except_id: int | None = None) -> bool:
    stmt = sa.select(app_user.c.id).where(app_user.c.email == email)
    if except_id is not None:
        stmt = stmt.where(app_user.c.id != except_id)
    return conn.execute(stmt).first() is not None


def get_user(conn: sa.Connection, uid: int) -> dict:
    row = conn.execute(sa.select(app_user).where(app_user.c.id == uid)).mappings().first()
    if not row:
        raise UserError("Usuario no encontrado", 404)
    return dict(row)


def list_users(conn: sa.Connection) -> list[dict]:
    n_nits = (sa.select(org_supplier.c.org_id, sa.func.count().label("n")).group_by(org_supplier.c.org_id).subquery())
    rows = conn.execute(
        sa.select(app_user, organization.c.name.label("company"), sa.func.coalesce(n_nits.c.n, 0).label("n_nits"))
        .select_from(app_user.outerjoin(organization, organization.c.id == app_user.c.org_id)
                     .outerjoin(n_nits, n_nits.c.org_id == app_user.c.org_id))
        .order_by(app_user.c.created_at.desc(), app_user.c.id.desc())).mappings().all()
    return [dict(r) for r in rows]


def create_user(conn: sa.Connection, *, email: str, name: str = "", company: str = "", role: str = "member",
                password: str | None = None, nits: tuple[str, ...] = ()) -> tuple[int, str | None]:
    """Crea usuario + su organización. Sin `password` genera una clave temporal (se devuelve para
    enviarla por correo) y obliga a cambiarla en el primer acceso."""
    email = normalize_email(email)
    check_role(role)
    if _email_taken(conn, email):
        raise UserError("Ese correo ya existe", 409)
    temp = None
    if password is None:
        password = temp = temp_password()
    else:
        check_password(password)
    org_id = conn.execute(sa.insert(organization).values(name=company.strip() or email)).inserted_primary_key[0]
    for n in nits:
        conn.execute(sa.insert(org_supplier).values(org_id=org_id, supplier_id=n))
    uid = conn.execute(sa.insert(app_user).values(
        org_id=org_id, email=email, name=name.strip(), role=role, password_hash=hash_password(password),
        active=True, must_change_password=temp is not None)).inserted_primary_key[0]
    return uid, temp


def send_invitation(email: str, name: str, password: str, *, reset: bool = False) -> bool:
    url = settings.app_url
    title = "Restablecimos tu contraseña" if reset else "Te damos la bienvenida a GC Intelligence"
    html = (f'<div style="font-family:system-ui;max-width:480px"><h2>{title}</h2>'
            f'<p>Hola{" " + name if name else ""}, estos son tus datos para entrar:</p>'
            f'<p><b>Plataforma:</b> <a href="{url}">{url}</a><br><b>Correo:</b> {email}<br>'
            f'<b>Contraseña temporal:</b> <code style="font-size:16px">{password}</code></p>'
            '<p>Por seguridad, al entrar por primera vez te pediremos crear una contraseña nueva.</p></div>')
    subject = "[GC] Tu contraseña temporal" if reset else "[GC] Tu acceso a GC Intelligence"
    return send_email(email, subject, html)


def reset_password(conn: sa.Connection, uid: int) -> tuple[dict, str]:
    user = get_user(conn, uid)
    temp = temp_password()
    conn.execute(sa.update(app_user).where(app_user.c.id == uid)
                 .values(password_hash=hash_password(temp), must_change_password=True))
    return user, temp


def update_user(conn: sa.Connection, actor: dict, uid: int, changes: dict) -> dict:
    """Aplica solo las claves presentes en `changes`. Un administrador no puede quitarse a sí mismo
    el rol ni desactivarse (así siempre queda al menos un administrador activo)."""
    user = get_user(conn, uid)
    values: dict = {}
    if "email" in changes:
        email = normalize_email(changes["email"])
        if _email_taken(conn, email, uid):
            raise UserError("Ese correo ya existe", 409)
        values["email"] = email
    if "name" in changes:
        values["name"] = (changes["name"] or "").strip()
    if "role" in changes:
        values["role"] = check_role(changes["role"])
    if "active" in changes:
        values["active"] = bool(changes["active"])
    if "perm_overrides" in changes:
        try:
            values["perm_overrides"] = normalize_overrides(changes["perm_overrides"])
        except ValueError as e:
            raise UserError(str(e)) from e
    if uid == actor["id"] and (values.get("role", user["role"]) != user["role"] or values.get("active", True) is False):
        raise UserError("No puedes cambiar tu propio rol ni desactivar tu cuenta", 409)
    if values:
        conn.execute(sa.update(app_user).where(app_user.c.id == uid).values(**values))
    if "company" in changes and changes["company"] is not None and changes["company"].strip():
        conn.execute(sa.update(organization).where(organization.c.id == user["org_id"]).values(name=changes["company"].strip()))
    return get_user(conn, uid)


def delete_user(conn: sa.Connection, actor: dict, uid: int) -> None:
    """Baja definitiva: borra al usuario y todo lo suyo (favoritos, opiniones, alertas, NIT, inventario)."""
    if uid == actor["id"]:
        raise UserError("No puedes eliminar tu propia cuenta", 409)
    user = get_user(conn, uid)
    searches = sa.select(saved_search.c.id).where(saved_search.c.user_id == uid)
    conn.execute(sa.delete(alert_delivery).where(alert_delivery.c.saved_search_id.in_(searches)))
    for t in (alert_sent, favorite, feedback, saved_search):
        conn.execute(sa.delete(t).where(t.c.user_id == uid))
    conn.execute(sa.delete(app_user).where(app_user.c.id == uid))
    org_id = user["org_id"]
    if not conn.execute(sa.select(app_user.c.id).where(app_user.c.org_id == org_id)).first():  # nadie más la usa
        for t in (org_supplier, inventory_item, inventory_alert):
            conn.execute(sa.delete(t).where(t.c.org_id == org_id))
        conn.execute(sa.delete(organization).where(organization.c.id == org_id))
