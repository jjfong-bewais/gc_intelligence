from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import settings
from ..db import get_conn, utcnow
from ..models import (alert_delivery, favorite, feedback, inventory_item, org_supplier, saved_search, tender)
from ..security import current_user
from ..services.alerts import run_saved_searches
from ..services.inventory import import_inventory, parse_csv
from ..services.recommend import inventory_matches
from ..services.search import Filters, hydrate, search_tenders

router = APIRouter(tags=["workspace"])

FAV_STATUS = {"por_cotizar", "cotizado", "ganado", "perdido", "descartado"}


def _need_tender(conn, ocid: str) -> None:
    if not conn.execute(sa.select(tender.c.ocid).where(tender.c.ocid == ocid)).first():
        raise HTTPException(404, "Concurso no encontrado")


# ---- NIT propios
class Nits(BaseModel):
    supplier_ids: list[str]


@router.put("/org/suppliers")
def set_nits(body: Nits, user=Depends(current_user), conn=Depends(get_conn)):
    ids = sorted({s.strip() for s in body.supplier_ids if s.strip()})
    ids = [s if s.startswith("GT-NIT-") else f"GT-NIT-{s}" for s in ids]
    conn.execute(sa.delete(org_supplier).where(org_supplier.c.org_id == user["org_id"]))
    if ids:
        conn.execute(sa.insert(org_supplier), [{"org_id": user["org_id"], "supplier_id": s} for s in ids])
    return {"supplier_ids": ids}


# ---- favoritos
class FavBody(BaseModel):
    status: str = "por_cotizar"
    note: str = ""


@router.get("/favorites")
def list_favs(user=Depends(current_user), conn=Depends(get_conn)):
    rows = conn.execute(sa.select(favorite).where(favorite.c.user_id == user["id"]).order_by(favorite.c.created_at.desc())).mappings().all()
    items = hydrate(conn, [{"ocid": r["ocid"]} for r in rows], user["id"])
    notes = {r["ocid"]: r for r in rows}
    for i in items:
        i["note"] = notes[i["ocid"]]["note"]
    return {"items": items}


@router.put("/favorites/{ocid}")
def put_fav(ocid: str, body: FavBody, user=Depends(current_user), conn=Depends(get_conn)):
    _need_tender(conn, ocid)
    if body.status not in FAV_STATUS:
        raise HTTPException(400, "Estado inválido")
    cur = conn.execute(sa.select(favorite.c.ocid).where(favorite.c.user_id == user["id"], favorite.c.ocid == ocid)).first()
    if cur:
        conn.execute(sa.update(favorite).where(favorite.c.user_id == user["id"], favorite.c.ocid == ocid)
                     .values(status=body.status, note=body.note))
    else:
        conn.execute(sa.insert(favorite).values(user_id=user["id"], ocid=ocid, status=body.status, note=body.note, created_at=utcnow()))
    return {"ok": True}


@router.delete("/favorites/{ocid}")
def del_fav(ocid: str, user=Depends(current_user), conn=Depends(get_conn)):
    conn.execute(sa.delete(favorite).where(favorite.c.user_id == user["id"], favorite.c.ocid == ocid))
    return {"ok": True}


# ---- feedback
class FbBody(BaseModel):
    signal: int
    reason: str = ""
    context: str = ""


def save_feedback(conn, user_id: int, ocid: str, signal: int, reason: str = "", context: str = "") -> None:
    if signal == 0:
        conn.execute(sa.delete(feedback).where(feedback.c.user_id == user_id, feedback.c.ocid == ocid))
        return
    signal = 1 if signal > 0 else -1
    cur = conn.execute(sa.select(feedback.c.ocid).where(feedback.c.user_id == user_id, feedback.c.ocid == ocid)).first()
    vals = dict(signal=signal, reason=reason[:40], context=context[:40])
    if cur:
        conn.execute(sa.update(feedback).where(feedback.c.user_id == user_id, feedback.c.ocid == ocid).values(**vals))
    else:
        conn.execute(sa.insert(feedback).values(user_id=user_id, ocid=ocid, created_at=utcnow(), **vals))


@router.put("/feedback/{ocid}")
def put_feedback(ocid: str, body: FbBody, user=Depends(current_user), conn=Depends(get_conn)):
    _need_tender(conn, ocid)
    save_feedback(conn, user["id"], ocid, body.signal, body.reason, body.context)
    return {"ok": True}


# ---- búsquedas guardadas
class SavedBody(BaseModel):
    name: str
    q: str = ""
    mode: str = "hybrid"
    filters: dict = {}
    frequency: str = "daily"
    active: bool = True


def _own(conn, sid: int, user) -> dict:
    r = conn.execute(sa.select(saved_search).where(saved_search.c.id == sid, saved_search.c.user_id == user["id"])).mappings().first()
    if not r:
        raise HTTPException(404, "Búsqueda no encontrada")
    return dict(r)


def _ser(r: dict) -> dict:
    return {k: (v.isoformat() + "Z" if hasattr(v, "isoformat") else v) for k, v in r.items()}


def _check(b: SavedBody) -> None:
    if b.frequency not in ("immediate", "daily", "weekly"):
        raise HTTPException(400, "Frecuencia inválida")
    if b.mode not in ("keyword", "semantic", "hybrid"):
        raise HTTPException(400, "Modo inválido")


@router.get("/saved-searches")
def list_saved(user=Depends(current_user), conn=Depends(get_conn)):
    rows = conn.execute(sa.select(saved_search).where(saved_search.c.user_id == user["id"]).order_by(saved_search.c.id)).mappings().all()
    return {"items": [_ser(dict(r)) for r in rows]}


@router.post("/saved-searches")
def create_saved(body: SavedBody, user=Depends(current_user), conn=Depends(get_conn)):
    _check(body)
    sid = conn.execute(sa.insert(saved_search).values(
        user_id=user["id"], name=body.name, q=body.q, mode=body.mode, filters=body.filters,
        frequency=body.frequency, active=body.active, last_run_at=utcnow(), created_at=utcnow(),
    )).inserted_primary_key[0]
    return _ser(_own(conn, sid, user))


@router.put("/saved-searches/{sid}")
def update_saved(sid: int, body: SavedBody, user=Depends(current_user), conn=Depends(get_conn)):
    _own(conn, sid, user)
    _check(body)
    conn.execute(sa.update(saved_search).where(saved_search.c.id == sid).values(
        name=body.name, q=body.q, mode=body.mode, filters=body.filters, frequency=body.frequency, active=body.active))
    return _ser(_own(conn, sid, user))


@router.delete("/saved-searches/{sid}")
def delete_saved(sid: int, user=Depends(current_user), conn=Depends(get_conn)):
    _own(conn, sid, user)
    conn.execute(sa.delete(alert_delivery).where(alert_delivery.c.saved_search_id == sid))
    conn.execute(sa.delete(saved_search).where(saved_search.c.id == sid))
    return {"ok": True}


@router.get("/saved-searches/{sid}/preview")
def preview_saved(sid: int, user=Depends(current_user), conn=Depends(get_conn)):
    s = _own(conn, sid, user)
    hits, total = search_tenders(conn, s["q"], s["mode"], Filters.from_dict(s["filters"]), limit=20)
    return {"total": total, "items": hydrate(conn, hits, user["id"])}


# ---- inventario
@router.get("/inventory")
def list_inventory(user=Depends(current_user), conn=Depends(get_conn)):
    rows = conn.execute(sa.select(inventory_item.c.id, inventory_item.c.sku, inventory_item.c.description,
                                  inventory_item.c.unit, inventory_item.c.unspsc)
                        .where(inventory_item.c.org_id == user["org_id"]).order_by(inventory_item.c.id).limit(1000)).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.post("/inventory/import")
async def import_inv(file: UploadFile, replace: bool = True, user=Depends(current_user), conn=Depends(get_conn)):
    raw = await file.read()
    if len(raw) > 5_000_000:
        raise HTTPException(413, "Archivo demasiado grande (máx. 5 MB)")
    try:
        rows = parse_csv(raw.decode("utf-8-sig", errors="replace"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"imported": import_inventory(conn, user["org_id"], rows, replace)}


@router.delete("/inventory")
def clear_inventory(user=Depends(current_user), conn=Depends(get_conn)):
    conn.execute(sa.delete(inventory_item).where(inventory_item.c.org_id == user["org_id"]))
    return {"ok": True}


@router.get("/inventory/matches")
def inv_matches(limit: int = 40, user=Depends(current_user), conn=Depends(get_conn)):
    found = inventory_matches(conn, user["org_id"], settings.match_threshold, limit=limit)
    items = hydrate(conn, found, user["id"])
    by = {f["ocid"]: f for f in found}
    for i in items:
        i["matches"] = by[i["ocid"]]["matches"]
    return {"items": items}


@router.post("/alerts/run")
def run_my_alerts(user=Depends(current_user), conn=Depends(get_conn)):
    return run_saved_searches(conn, force=True)
