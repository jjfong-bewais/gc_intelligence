from __future__ import annotations

import re

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel

from ..config import settings
from ..db import get_conn, utcnow
from ..models import (alert_delivery, alert_sent, favorite, feedback, inventory_item, org_supplier, party, saved_search, tender)
from ..services.history import org_history
from ..permissions import Perm, require
from ..security import current_user
from ..services import usage
from ..services.alerts import REPEAT_WINDOW, pick_for_saved, run_saved_searches
from ..services.inventory import import_inventory, parse_csv
from ..services.recommend import build_profile, inventory_matches
from ..services.search import Filters, accepting_cond, build_conds, hydrate, search_tenders

router = APIRouter(tags=["workspace"])

FAV_STATUS = {"por_cotizar", "cotizado", "ganado", "perdido", "descartado"}


def _need_tender(conn, ocid: str) -> None:
    if not conn.execute(sa.select(tender.c.ocid).where(tender.c.ocid == ocid)).first():
        raise HTTPException(404, "Concurso no encontrado")


# ---- NIT propios
class Nits(BaseModel):
    supplier_ids: list[str]


NIT_RE = re.compile(r"^[0-9]{1,14}K?$")


def norm_nit(raw: str) -> str:
    """'GT-NIT-1234567-8', '1234567-8', ' 104812869 ' → 'GT-NIT-12345678' (sin guiones ni espacios)."""
    s = raw.strip().upper()
    if s.startswith("GT-NIT-"):
        s = s[7:]
    s = re.sub(r"[\s\-.]", "", s)
    if not NIT_RE.match(s):
        raise HTTPException(400, "El NIT solo puede tener números (y una K al final)")
    return f"GT-NIT-{s}"


def _org_nits(conn, org_id: int) -> list[dict]:
    rows = conn.execute(sa.select(org_supplier.c.supplier_id, org_supplier.c.label, party.c.name)
                        .select_from(org_supplier.outerjoin(party, party.c.id == org_supplier.c.supplier_id))
                        .where(org_supplier.c.org_id == org_id).order_by(org_supplier.c.label, org_supplier.c.supplier_id)).all()
    return [{"id": s, "nit": s.replace("GT-NIT-", ""), "label": lbl or "", "name": name, "found": name is not None}
            for s, lbl, name in rows]


class NitBody(BaseModel):
    nit: str
    label: str = ""


def _label(b: NitBody) -> str:
    lbl = b.label.strip()
    if not lbl:
        raise HTTPException(400, "Escribe un nombre de identificación")
    return lbl[:200]


@router.get("/org/suppliers")
def list_nits(user=Depends(current_user), conn=Depends(get_conn)):
    return {"items": _org_nits(conn, user["org_id"])}


@router.post("/org/suppliers")
def add_nit(body: NitBody, user=Depends(current_user), conn=Depends(get_conn)):
    sid, lbl = norm_nit(body.nit), _label(body)
    if conn.execute(sa.select(org_supplier.c.supplier_id).where(org_supplier.c.org_id == user["org_id"],
                                                                org_supplier.c.supplier_id == sid)).first():
        raise HTTPException(409, "Ese NIT ya está en tu lista")
    conn.execute(sa.insert(org_supplier).values(org_id=user["org_id"], supplier_id=sid, label=lbl))
    return {"items": _org_nits(conn, user["org_id"])}


@router.put("/org/suppliers/{nit}")
def update_nit(nit: str, body: NitBody, user=Depends(current_user), conn=Depends(get_conn)):
    old, new, lbl = norm_nit(nit), norm_nit(body.nit), _label(body)
    where = (org_supplier.c.org_id == user["org_id"], org_supplier.c.supplier_id == old)
    if not conn.execute(sa.select(org_supplier.c.supplier_id).where(*where)).first():
        raise HTTPException(404, "NIT no encontrado")
    if new != old and conn.execute(sa.select(org_supplier.c.supplier_id).where(
            org_supplier.c.org_id == user["org_id"], org_supplier.c.supplier_id == new)).first():
        raise HTTPException(409, "Ese NIT ya está en tu lista")
    conn.execute(sa.update(org_supplier).where(*where).values(supplier_id=new, label=lbl))
    return {"items": _org_nits(conn, user["org_id"])}


@router.delete("/org/suppliers/{nit}")
def delete_nit(nit: str, user=Depends(current_user), conn=Depends(get_conn)):
    conn.execute(sa.delete(org_supplier).where(org_supplier.c.org_id == user["org_id"],
                                               org_supplier.c.supplier_id == norm_nit(nit)))
    return {"items": _org_nits(conn, user["org_id"])}


@router.put("/org/suppliers")
def set_nits(body: Nits, user=Depends(current_user), conn=Depends(get_conn)):
    """Reemplazo masivo (compatibilidad); conserva el nombre de los NIT que se mantienen."""
    ids = sorted({norm_nit(s) for s in body.supplier_ids if s.strip()})
    keep = dict(conn.execute(sa.select(org_supplier.c.supplier_id, org_supplier.c.label)
                             .where(org_supplier.c.org_id == user["org_id"])).all())
    conn.execute(sa.delete(org_supplier).where(org_supplier.c.org_id == user["org_id"]))
    if ids:
        conn.execute(sa.insert(org_supplier), [{"org_id": user["org_id"], "supplier_id": s, "label": keep.get(s, "")} for s in ids])
    return {"supplier_ids": ids}


@router.get("/org/history")
def history(user=Depends(current_user), conn=Depends(get_conn)):
    """Resumen del histórico en Guatecompras de los NIT de la organización."""
    labels = dict(conn.execute(sa.select(org_supplier.c.supplier_id, org_supplier.c.label)
                               .where(org_supplier.c.org_id == user["org_id"])).all())
    return org_history(conn, labels)


# ---- favoritos
class FavBody(BaseModel):
    status: str = "por_cotizar"
    note: str = ""


@router.get("/favorites")
def list_favs(user=Depends(require(Perm.FAVORITES)), conn=Depends(get_conn)):
    rows = conn.execute(sa.select(favorite).where(favorite.c.user_id == user["id"]).order_by(favorite.c.created_at.desc())).mappings().all()
    items = hydrate(conn, [{"ocid": r["ocid"]} for r in rows], user["id"])
    notes = {r["ocid"]: r for r in rows}
    for i in items:
        i["note"] = notes[i["ocid"]]["note"]
    return {"items": items}


@router.put("/favorites/{ocid}")
def put_fav(ocid: str, body: FavBody, request: Request, user=Depends(require(Perm.FAVORITES)), conn=Depends(get_conn)):
    _need_tender(conn, ocid)
    if body.status not in FAV_STATUS:
        raise HTTPException(400, "Estado inválido")
    cur = conn.execute(sa.select(favorite.c.ocid).where(favorite.c.user_id == user["id"], favorite.c.ocid == ocid)).first()
    usage.note(request, ocid=ocid, status=body.status, action="update" if cur else "save")
    if cur:
        conn.execute(sa.update(favorite).where(favorite.c.user_id == user["id"], favorite.c.ocid == ocid)
                     .values(status=body.status, note=body.note))
    else:
        conn.execute(sa.insert(favorite).values(user_id=user["id"], ocid=ocid, status=body.status, note=body.note, created_at=utcnow()))
    return {"ok": True}


@router.delete("/favorites/{ocid}")
def del_fav(ocid: str, user=Depends(require(Perm.FAVORITES)), conn=Depends(get_conn)):
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
def put_feedback(ocid: str, body: FbBody, request: Request, user=Depends(require(Perm.FAVORITES)), conn=Depends(get_conn)):
    _need_tender(conn, ocid)
    usage.note(request, ocid=ocid, signal=body.signal, context=body.context[:40])
    save_feedback(conn, user["id"], ocid, body.signal, body.reason, body.context)
    return {"ok": True}


# ---- búsquedas guardadas
class SavedBody(BaseModel):
    name: str
    q: str = ""
    mode: str = "hybrid"
    filters: dict = {}
    frequency: str = "daily"
    active: bool = True  # enviar correos
    max_items: int = 5  # concursos por correo (1-10)


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
    if not 1 <= b.max_items <= 10:
        raise HTTPException(400, "La cantidad por correo debe estar entre 1 y 10")
    if not b.name.strip():
        raise HTTPException(400, "Ponle un nombre a la combinación")


@router.get("/saved-searches")
def list_saved(user=Depends(require(Perm.ALERTS)), conn=Depends(get_conn)):
    rows = conn.execute(sa.select(saved_search).where(saved_search.c.user_id == user["id"]).order_by(saved_search.c.id)).mappings().all()
    return {"items": [_ser(dict(r)) for r in rows]}


@router.post("/saved-searches")
def create_saved(body: SavedBody, request: Request, user=Depends(require(Perm.ALERTS)), conn=Depends(get_conn)):
    _check(body)
    usage.note(request, q=body.q[:300], mode=body.mode, frequency=body.frequency)
    sid = conn.execute(sa.insert(saved_search).values(
        user_id=user["id"], name=body.name.strip(), q=body.q, mode=body.mode, filters=body.filters,
        frequency=body.frequency, active=body.active, max_items=body.max_items, last_run_at=None, created_at=utcnow(),
    )).inserted_primary_key[0]
    return _ser(_own(conn, sid, user))


@router.put("/saved-searches/{sid}")
def update_saved(sid: int, body: SavedBody, user=Depends(require(Perm.ALERTS)), conn=Depends(get_conn)):
    _own(conn, sid, user)
    _check(body)
    conn.execute(sa.update(saved_search).where(saved_search.c.id == sid).values(
        name=body.name.strip(), q=body.q, mode=body.mode, filters=body.filters, frequency=body.frequency,
        active=body.active, max_items=body.max_items))
    return _ser(_own(conn, sid, user))


@router.delete("/saved-searches/{sid}")
def delete_saved(sid: int, user=Depends(require(Perm.ALERTS)), conn=Depends(get_conn)):
    _own(conn, sid, user)
    conn.execute(sa.delete(alert_delivery).where(alert_delivery.c.saved_search_id == sid))
    conn.execute(sa.delete(saved_search).where(saved_search.c.id == sid))
    return {"ok": True}


@router.get("/saved-searches/{sid}/preview")
def preview_saved(sid: int, user=Depends(require(Perm.ALERTS)), conn=Depends(get_conn)):
    """Cuántos concursos vigentes cumplen la combinación y cuáles irían en el próximo correo."""
    s = _own(conn, sid, user)
    now = utcnow()
    f = Filters.from_dict(s["filters"])
    _, total = search_tenders(conn, s["q"], s["mode"], f, limit=1, extra_conds=[accepting_cond(now), *build_conds(f)])
    sids = list(conn.execute(sa.select(org_supplier.c.supplier_id).where(org_supplier.c.org_id == user["org_id"])).scalars())
    prof = build_profile(conn, sids, user["id"])
    ex = set(conn.execute(sa.select(alert_sent.c.ocid).where(
        alert_sent.c.user_id == user["id"], alert_sent.c.sent_at > now - REPEAT_WINDOW)).scalars())
    ex |= set(conn.execute(sa.select(favorite.c.ocid).where(favorite.c.user_id == user["id"])).scalars()) | set(prof["negatives"])
    picks = pick_for_saved(conn, s, prof, ex, now)
    items = hydrate(conn, picks, user["id"])
    by = {p["ocid"]: p for p in picks}
    for i in items:
        i["reason"] = by[i["ocid"]]["reason"]
    return {"total": total, "items": items}


# ---- inventario
@router.get("/inventory")
def list_inventory(user=Depends(require(Perm.INVENTORY)), conn=Depends(get_conn)):
    rows = conn.execute(sa.select(inventory_item.c.id, inventory_item.c.sku, inventory_item.c.description,
                                  inventory_item.c.unit, inventory_item.c.unspsc)
                        .where(inventory_item.c.org_id == user["org_id"]).order_by(inventory_item.c.id).limit(1000)).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.post("/inventory/import")
async def import_inv(file: UploadFile, request: Request, replace: bool = True, user=Depends(require(Perm.INVENTORY)), conn=Depends(get_conn)):
    raw = await file.read()
    if len(raw) > 5_000_000:
        raise HTTPException(413, "Archivo demasiado grande (máx. 5 MB)")
    try:
        rows = parse_csv(raw.decode("utf-8-sig", errors="replace"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    n = import_inventory(conn, user["org_id"], rows, replace)
    usage.note(request, rows=n if isinstance(n, int) else len(rows))
    return {"imported": n}


@router.delete("/inventory")
def clear_inventory(user=Depends(require(Perm.INVENTORY)), conn=Depends(get_conn)):
    conn.execute(sa.delete(inventory_item).where(inventory_item.c.org_id == user["org_id"]))
    return {"ok": True}


@router.get("/inventory/matches")
def inv_matches(limit: int = 40, user=Depends(require(Perm.INVENTORY)), conn=Depends(get_conn)):
    found = inventory_matches(conn, user["org_id"], settings.match_threshold, limit=limit)
    items = hydrate(conn, found, user["id"])
    by = {f["ocid"]: f for f in found}
    for i in items:
        i["matches"] = by[i["ocid"]]["matches"]
    return {"items": items}


@router.post("/alerts/run")
def run_my_alerts(user=Depends(require(Perm.ALERTS)), conn=Depends(get_conn)):
    return run_saved_searches(conn, force=True, user_id=user["id"])
