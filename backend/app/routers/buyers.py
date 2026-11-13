"""Perfil de entidad compradora: qué compra, cuánto adjudica y a quién."""
from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_conn
from ..models import award, tender
from ..permissions import Perm, require
from ..services.search import hydrate

router = APIRouter(prefix="/buyers", tags=["buyers"])


@router.get("/profile")
def profile(name: str = Query(..., min_length=2), user=Depends(require(Perm.SEARCH)), conn=Depends(get_conn)):
    base = tender.c.buyer_name == name
    n = conn.execute(sa.select(sa.func.count()).select_from(tender).where(base)).scalar()
    if not n:
        raise HTTPException(404, "Entidad no encontrada")
    open_n = conn.execute(sa.select(sa.func.count()).select_from(tender).where(base, tender.c.status_details == "Vigente")).scalar()
    avg_b = conn.execute(sa.select(sa.func.avg(tender.c.n_tenderers)).where(base, tender.c.n_tenderers > 0)).scalar()
    awarded = conn.execute(
        sa.select(sa.func.count(sa.distinct(award.c.ocid)), sa.func.coalesce(sa.func.sum(award.c.amount), 0))
        .select_from(award.join(tender, tender.c.ocid == award.c.ocid)).where(base)).first()
    winners = conn.execute(
        sa.select(award.c.supplier_id, award.c.supplier_name, sa.func.count(sa.distinct(award.c.ocid)).label("n"),
                  sa.func.sum(award.c.amount))
        .select_from(award.join(tender, tender.c.ocid == award.c.ocid)).where(base, award.c.supplier_id.is_not(None))
        .group_by(award.c.supplier_id, award.c.supplier_name).order_by(sa.desc("n")).limit(10)).all()
    # Se agrupa por clase en Python: en Postgres substr(col, :1, :2) del SELECT y del GROUP BY no se reconocen como la misma expresión.
    by_class: dict[str, int] = {}
    for code, k in conn.execute(sa.select(tender.c.unspsc_main, sa.func.count())
                                .where(base, tender.c.unspsc_main.is_not(None)).group_by(tender.c.unspsc_main)):
        by_class[code[:6]] = by_class.get(code[:6], 0) + k
    classes = sorted(by_class.items(), key=lambda x: -x[1])[:8]
    methods = conn.execute(
        sa.select(tender.c.method_details, sa.func.count().label("n")).where(base, tender.c.method_details.is_not(None))
        .group_by(tender.c.method_details).order_by(sa.desc("n")).limit(6)).all()
    recent = conn.execute(sa.select(tender.c.ocid).where(base).order_by(tender.c.published_at.desc()).limit(10)).scalars().all()
    return {
        "name": name, "tenders": n, "open": open_n, "avg_bidders": round(float(avg_b), 1) if avg_b else None,
        "awarded_tenders": awarded[0], "awarded_total": float(awarded[1] or 0),
        "top_winners": [{"id": r[0], "name": r[1], "n": r[2], "amount": float(r[3] or 0)} for r in winners],
        "top_classes": [{"unspsc": c, "n": k} for c, k in classes],
        "methods": [{"name": m, "n": k} for m, k in methods],
        "recent": hydrate(conn, [{"ocid": o} for o in recent], user["id"]),
    }
