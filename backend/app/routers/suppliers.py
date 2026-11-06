from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException

from ..db import get_conn
from ..models import award, bid, party, tender
from ..security import current_user
from ..services.opportunities import find_peers
from ..services.recommend import build_profile, recommend_open
from ..services.search import hydrate
from ..services.text import normalize

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("")
def search(q: str = "", limit: int = 20, user=Depends(current_user), conn=Depends(get_conn)):
    stmt = sa.select(party.c.id, party.c.name).where(party.c.kind == "supplier")
    if q.strip():
        n = normalize(q)
        stmt = stmt.where(sa.or_(party.c.name_norm.like(f"%{n}%"), party.c.id.like(f"%{q.strip()}%")))
    rows = conn.execute(stmt.order_by(party.c.name).limit(min(limit, 50))).all()
    return {"items": [{"id": r[0], "name": r[1]} for r in rows]}


def _exists(conn, sid: str) -> dict:
    p = conn.execute(sa.select(party).where(party.c.id == sid)).mappings().first()
    if not p:
        raise HTTPException(404, "Proveedor no encontrado")
    return dict(p)


@router.get("/{sid}")
def profile(sid: str, user=Depends(current_user), conn=Depends(get_conn)):
    p = _exists(conn, sid)
    won = conn.execute(sa.select(sa.func.count(sa.distinct(award.c.ocid)), sa.func.coalesce(sa.func.sum(award.c.amount), 0))
                       .where(award.c.supplier_id == sid)).one()
    bids = conn.execute(sa.select(sa.func.count(sa.distinct(bid.c.ocid))).where(bid.c.supplier_id == sid)).scalar()
    classes = conn.execute(
        sa.select(tender.c.unspsc_main, sa.func.count().label("n"))
        .where(tender.c.ocid.in_(sa.select(bid.c.ocid).where(bid.c.supplier_id == sid).union(
            sa.select(award.c.ocid).where(award.c.supplier_id == sid))), tender.c.unspsc_main.is_not(None))
        .group_by(tender.c.unspsc_main).order_by(sa.desc("n")).limit(8)).all()
    buyers = conn.execute(
        sa.select(tender.c.buyer_name, sa.func.count().label("n")).where(tender.c.ocid.in_(
            sa.select(award.c.ocid).where(award.c.supplier_id == sid))).group_by(tender.c.buyer_name)
        .order_by(sa.desc("n")).limit(8)).all()
    return {"id": sid, "name": p["name"], "awarded_tenders": won[0], "awarded_total": float(won[1]),
            "bid_tenders": bids, "top_classes": [{"unspsc": c, "n": n} for c, n in classes],
            "top_buyers": [{"name": b, "n": n} for b, n in buyers]}


@router.get("/{sid}/tenders")
def tenders(sid: str, role: str = "awarded", limit: int = 30, user=Depends(current_user), conn=Depends(get_conn)):
    _exists(conn, sid)
    t = award if role == "awarded" else bid
    ocids = conn.execute(sa.select(t.c.ocid).where(t.c.supplier_id == sid).distinct()).scalars().all()
    rows = conn.execute(sa.select(tender.c.ocid).where(tender.c.ocid.in_(ocids)).order_by(tender.c.published_at.desc()).limit(limit)).scalars().all()
    return {"items": hydrate(conn, [{"ocid": o} for o in rows], user["id"])}


@router.get("/{sid}/matching-tenders")
def matching(sid: str, limit: int = 30, user=Depends(current_user), conn=Depends(get_conn)):
    _exists(conn, sid)
    prof = build_profile(conn, [sid], user["id"])
    recs = recommend_open(conn, prof, k=limit)
    return {"items": hydrate(conn, recs, user["id"])}


@router.get("/{sid}/peers")
def peers(sid: str, user=Depends(current_user), conn=Depends(get_conn)):
    _exists(conn, sid)
    return {"items": find_peers(conn, [sid])}
