from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ..config import settings
from ..db import get_conn
from ..models import app_user, org_supplier, organization
from ..permissions import permission_names
from ..security import COOKIE, current_user, hash_password, make_session, session_user, verify_password
from ..services.users import UserError, check_password, normalize_email

router = APIRouter(prefix="/auth", tags=["auth"])


class Login(BaseModel):
    email: str
    password: str


def public_user(conn, u: dict) -> dict:
    org = conn.execute(sa.select(organization.c.name).where(organization.c.id == u["org_id"])).scalar()
    nits = conn.execute(sa.select(org_supplier.c.supplier_id).where(org_supplier.c.org_id == u["org_id"])).scalars().all()
    return {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"], "org_id": u["org_id"],
            "org_name": org, "supplier_ids": list(nits), "demo": settings.gc_mode == "demo",
            "permissions": permission_names(u), "must_change_password": u["must_change_password"]}


def _set_cookie(resp: Response, uid: int) -> None:
    resp.set_cookie(COOKIE, make_session(uid), max_age=settings.session_days * 86400, httponly=True,
                    secure=settings.cookie_secure, samesite=settings.cookie_samesite, domain=settings.cookie_domain)


@router.post("/login")
def login(body: Login, resp: Response, conn=Depends(get_conn)):
    u = conn.execute(sa.select(app_user).where(app_user.c.email == body.email.strip().lower())).mappings().first()
    if not u or not verify_password(body.password, u["password_hash"]):
        raise HTTPException(401, "Correo o contraseña incorrectos")
    if not u["active"]:
        raise HTTPException(403, "Tu cuenta está desactivada. Escribe al administrador.")
    _set_cookie(resp, u["id"])
    return public_user(conn, dict(u))


@router.post("/logout")
def logout(resp: Response):
    resp.delete_cookie(COOKIE, domain=settings.cookie_domain)
    return {"ok": True}


@router.get("/me")
def me(user=Depends(session_user), conn=Depends(get_conn)):
    return public_user(conn, user)


class EmailChange(BaseModel):
    email: str
    password: str


@router.put("/email")
def change_email(body: EmailChange, user=Depends(current_user), conn=Depends(get_conn)):
    """Cambia el correo de la cuenta (con él se inicia sesión y a él llegan las alertas)."""
    email = normalize_email(body.email)
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(403, "La contraseña no es correcta")
    if email != user["email"] and conn.execute(sa.select(app_user.c.id).where(app_user.c.email == email)).first():
        raise HTTPException(409, "Ese correo ya está en uso")
    conn.execute(sa.update(app_user).where(app_user.c.id == user["id"]).values(email=email))
    u = conn.execute(sa.select(app_user).where(app_user.c.id == user["id"])).mappings().first()
    return public_user(conn, dict(u))


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.put("/password")
def change_password(body: PasswordChange, user=Depends(session_user), conn=Depends(get_conn)):
    """Cambia la contraseña. También es la salida obligada tras entrar con una clave temporal."""
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(403, "La contraseña actual no es correcta")
    check_password(body.new_password)
    if body.new_password == body.current_password:
        raise UserError("La contraseña nueva debe ser distinta de la actual")
    conn.execute(sa.update(app_user).where(app_user.c.id == user["id"])
                 .values(password_hash=hash_password(body.new_password), must_change_password=False))
    u = conn.execute(sa.select(app_user).where(app_user.c.id == user["id"])).mappings().first()
    return public_user(conn, dict(u))
