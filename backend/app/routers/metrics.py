"""Métricas de uso (solo rol admin) y recepción de la telemetría del navegador."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..db import get_conn, utcnow
from ..permissions import Perm, require
from ..security import current_user
from ..services import metrics as svc
from ..services import usage

router = APIRouter(tags=["metrics"])
admin = require(Perm.ADMIN)
Days = Query(30, ge=1, le=90, description="Ventana en días (máx. 90, lo que se conserva)")


# ---- telemetría del navegador (cualquier usuario autenticado)
class TEvent(BaseModel):
    type: Literal["page_view", "heartbeat", "action"]
    path: str = Field("", max_length=200)
    src: str = Field("", max_length=20)
    seconds: int = Field(0, ge=0, le=3600)
    name: str = Field("", max_length=40)


class Telemetry(BaseModel):
    events: list[TEvent] = Field(max_length=50)


@router.post("/telemetry")
def telemetry(body: Telemetry, request: Request, user=Depends(current_user)):
    """Pantallas vistas y tiempo activo. Se guarda en segundo plano; responde de inmediato."""
    device = usage.device_of(request.headers.get("user-agent", ""))
    for e in body.events:
        base = {"ts": utcnow(), "user_id": user["id"], "device": device, "src": e.src if e.src == "alert" else ""}
        if e.type == "heartbeat":
            usage.enqueue({**base, "kind": "heartbeat", "seconds": e.seconds})
        elif e.type == "page_view":
            path = usage.normalize_path(e.path)
            usage.enqueue({**base, "kind": "page", "feature": usage.page_feature(path), "action": "view", "route": path,
                           "props": {"src": e.src} if e.src else None})
        elif re.fullmatch(r"[a-z_]{1,40}", e.name):
            usage.enqueue({**base, "kind": "action", "feature": usage.page_feature(usage.normalize_path(e.path)), "action": e.name,
                           "route": usage.normalize_path(e.path)})
    return {"ok": True}


# ---- consultas del panel
@router.get("/admin/metrics/overview")
def overview(days: int = Days, exclude_admins: bool = True, user=Depends(admin), conn=Depends(get_conn)):
    return svc.overview(conn, days, exclude_admins)


@router.get("/admin/metrics/users")
def users(days: int = Days, exclude_admins: bool = True, user=Depends(admin), conn=Depends(get_conn)):
    return svc.users(conn, days, exclude_admins)


@router.get("/admin/metrics/users/{uid}")
def user_detail(uid: int, days: int = Days, user=Depends(admin), conn=Depends(get_conn)):
    out = svc.user_detail(conn, uid, days)
    if not out:
        raise HTTPException(404, "Usuario no encontrado")
    return out


@router.get("/admin/metrics/features")
def features(days: int = Days, exclude_admins: bool = True, user=Depends(admin), conn=Depends(get_conn)):
    return svc.features(conn, days, exclude_admins)


@router.get("/admin/metrics/searches")
def searches(days: int = Days, exclude_admins: bool = True, user=Depends(admin), conn=Depends(get_conn)):
    return svc.searches(conn, days, exclude_admins)


@router.get("/admin/metrics/retention")
def retention(exclude_admins: bool = True, user=Depends(admin), conn=Depends(get_conn)):
    return svc.retention(conn, exclude_admins)


@router.get("/admin/metrics/health")
def health(days: int = Days, exclude_admins: bool = True, user=Depends(admin), conn=Depends(get_conn)):
    return svc.health(conn, days, exclude_admins)
