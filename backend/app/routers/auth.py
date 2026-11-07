from __future__ import annotations

import re

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ..config import settings
from ..db import get_conn
from ..models import app_user, org_supplier, organization
from ..security import COOKIE, current_user, hash_password, make_session, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class Login(BaseModel):
    email: str
    password: str


class Register(Login):
    name: str = ""
    org_name: str = ""


def public_user(conn, u: dict) -> dict:
    org = conn.execute(sa.select(organization.c.name).where(organization.c.id == u["org_id"])).scalar()
    nits = conn.execute(sa.select(org_supplier.c.supplier_id).where(org_supplier.c.org_id == u["org_id"])).scalars().all()
    return {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"], "org_id": u["org_id"],
            "org_name": org, "supplier_ids": list(nits), "demo": settings.gc_mode == "demo"}


def _set_cookie(resp: Response, uid: int) -> None:
    resp.set_cookie(COOKIE, make_session(uid), max_age=settings.session_days * 86400, httponly=True,
                    secure=settings.cookie_secure, samesite=settings.cookie_samesite, domain=settings.cookie_domain)


@router.post("/login")
def login(body: Login, resp: Response, conn=Depends(get_conn)):
    u = conn.execute(sa.select(app_user).where(app_user.c.email == body.email.strip().lower())).mappings().first()
    if not u or not verify_password(body.password, u["password_hash"]):
        raise HTTPException(401, "Correo o contraseña incorrectos")
    _set_cookie(resp, u["id"])
    return public_user(conn, dict(u))


@router.post("/register")
def register(body: Register, resp: Response, conn=Depends(get_conn)):
    if not settings.allow_signup:
        raise HTTPException(403, "El registro está deshabilitado")
    email = body.email.strip().lower()
    if len(body.password) < 8:
        raise HTTPException(400, "La contraseña necesita al menos 8 caracteres")
    if conn.execute(sa.select(app_user.c.id).where(app_user.c.email == email)).first():
        raise HTTPException(409, "Ese correo ya existe")
    org_id = conn.execute(sa.insert(organization).values(name=body.org_name or email)).inserted_primary_key[0]
    uid = conn.execute(sa.insert(app_user).values(
        org_id=org_id, email=email, name=body.name, password_hash=hash_password(body.password), role="admin"
    )).inserted_primary_key[0]
    _set_cookie(resp, uid)
    u = conn.execute(sa.select(app_user).where(app_user.c.id == uid)).mappings().first()
    return public_user(conn, dict(u))


@router.post("/logout")
def logout(resp: Response):
    resp.delete_cookie(COOKIE, domain=settings.cookie_domain)
    return {"ok": True}


@router.get("/me")
def me(user=Depends(current_user), conn=Depends(get_conn)):
    return public_user(conn, user)


class EmailChange(BaseModel):
    email: str
    password: str


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.put("/email")
def change_email(body: EmailChange, user=Depends(current_user), conn=Depends(get_conn)):
    """Cambia el correo de la cuenta (con él se inicia sesión y a él llegan las alertas)."""
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 200:
        raise HTTPException(400, "Escribe un correo válido")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(403, "La contraseña no es correcta")
    if email != user["email"] and conn.execute(sa.select(app_user.c.id).where(app_user.c.email == email)).first():
        raise HTTPException(409, "Ese correo ya está en uso")
    conn.execute(sa.update(app_user).where(app_user.c.id == user["id"]).values(email=email))
    u = conn.execute(sa.select(app_user).where(app_user.c.id == user["id"])).mappings().first()
    return public_user(conn, dict(u))
