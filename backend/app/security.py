"""Contraseñas (scrypt, solo biblioteca estándar), sesiones y enlaces firmados."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeSerializer, URLSafeTimedSerializer

from .config import settings
from .db import get_conn
from .models import app_user

COOKIE = "gc_session"
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(h)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, h = stored.split("$")
        calc = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(calc, base64.b64decode(h))
    except Exception:
        return False


_session = URLSafeTimedSerializer(settings.secret_key, salt="gc-session")
_link = URLSafeSerializer(settings.secret_key, salt="gc-link")


def make_session(user_id: int) -> str:
    return _session.dumps({"u": user_id})


def read_session(token: str) -> int | None:
    try:
        return int(_session.loads(token, max_age=settings.session_days * 86400)["u"])
    except (BadSignature, SignatureExpired, KeyError, ValueError):
        return None


def make_link(payload: dict) -> str:
    return _link.dumps(payload)


def read_link(token: str) -> dict | None:
    try:
        return _link.loads(token)
    except BadSignature:
        return None


def current_user(request: Request, conn: sa.Connection = Depends(get_conn)) -> dict:
    token = request.cookies.get(COOKIE)
    uid = read_session(token) if token else None
    row = conn.execute(sa.select(app_user).where(app_user.c.id == uid)).mappings().first() if uid else None
    if not row:
        raise HTTPException(status_code=401, detail="No autenticado")
    return dict(row)


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    return user
