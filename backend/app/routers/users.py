"""Administración de usuarios (solo rol admin). Cada alta envía una clave temporal por correo."""
from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..db import get_conn
from ..permissions import Perm, permission_names, require
from ..services import users as svc

router = APIRouter(prefix="/users", tags=["users"])
admin = require(Perm.ADMIN)


class NewUser(BaseModel):
    email: str
    name: str = ""
    company: str = ""
    role: str = "member"


class UserPatch(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    perm_overrides: Optional[dict] = None  # {"grant": [...], "deny": [...]}


def _out(u: dict) -> dict:
    return {"id": u["id"], "email": u["email"], "name": u["name"], "company": u.get("company"), "role": u["role"],
            "active": u["active"], "must_change_password": u["must_change_password"],
            "permissions": permission_names(u), "perm_overrides": u.get("perm_overrides") or {"grant": [], "deny": []},
            "n_nits": u.get("n_nits", 0), "created_at": u["created_at"].isoformat() if u.get("created_at") else None}


def _full(conn: sa.Connection, uid: int) -> dict:
    return _out(next(u for u in svc.list_users(conn) if u["id"] == uid))


@router.get("")
def list_users(user=Depends(admin), conn=Depends(get_conn)):
    return {"items": [_out(u) for u in svc.list_users(conn)]}


@router.post("")
def create_user(body: NewUser, user=Depends(admin), conn=Depends(get_conn)):
    uid, temp = svc.create_user(conn, email=body.email, name=body.name, company=body.company, role=body.role)
    sent = svc.send_invitation(body.email.strip().lower(), body.name, temp)
    return {"user": _full(conn, uid), "email_sent": sent}


@router.patch("/{uid}")
def update_user(uid: int, body: UserPatch, user=Depends(admin), conn=Depends(get_conn)):
    svc.update_user(conn, user, uid, body.model_dump(exclude_unset=True))
    return {"user": _full(conn, uid)}


@router.post("/{uid}/reset-password")
def reset_password(uid: int, user=Depends(admin), conn=Depends(get_conn)):
    """Genera otra clave temporal y la reenvía (sirve también para reenviar una invitación perdida)."""
    target, temp = svc.reset_password(conn, uid)
    return {"email_sent": svc.send_invitation(target["email"], target["name"], temp, reset=True)}


@router.delete("/{uid}")
def delete_user(uid: int, user=Depends(admin), conn=Depends(get_conn)):
    svc.delete_user(conn, user, uid)
    return {"ok": True}
