from __future__ import annotations

from datetime import timedelta

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query

from ..db import get_conn, utcnow
from ..models import award, favorite, inventory_item, org_supplier, tender
from ..permissions import Perm, require
from ..security import current_user
from ..services.opportunities import opportunities
from ..services.recommend import build_profile, inventory_matches, recommend_open
from ..services.search import build_conds, hydrate, open_cond, parse_filters_param
from ..config import settings

router = APIRouter(tags=["insights"])


def _sids(conn, user) -> list[str]:
    return list(conn.execute(sa.select(org_supplier.c.supplier_id).where(org_supplier.c.org_id == user["org_id"])).scalars())


FILTERS_HELP = "Filtros duros en JSON (mismo formato que /tenders/search)"


@router.get("/recommendations")
def recommendations(limit: int = 30, f: str = Query("", description=FILTERS_HELP),
                    user=Depends(require(Perm.RECOMMENDATIONS)), conn=Depends(get_conn)):
    """Siempre concursos vigentes; los filtros los acotan o excluyen."""
    conds = build_conds(parse_filters_param(f))
    prof = build_profile(conn, _sids(conn, user), user["id"])
    favs = set(conn.execute(sa.select(favorite.c.ocid).where(favorite.c.user_id == user["id"])).scalars())
    recs = recommend_open(conn, prof, k=limit, exclude=favs, conds=conds)
    return {"items": hydrate(conn, recs, user["id"]), "profile_size": len(prof["vectors"])}


@router.get("/opportunities")
def opps(f: str = Query("", description=FILTERS_HELP), user=Depends(require(Perm.OPPORTUNITIES)), conn=Depends(get_conn)):
    flt = parse_filters_param(f)
    return opportunities(conn, _sids(conn, user), conds=build_conds(flt) or None, key=flt.key())


@router.get("/dashboard")
def dashboard(f: str = Query("", description=FILTERS_HELP), user=Depends(current_user), conn=Depends(get_conn)):
    now = utcnow()
    conds = build_conds(parse_filters_param(f))
    sids = _sids(conn, user)
    open_total = conn.execute(sa.select(sa.func.count()).select_from(tender).where(open_cond(), *conds)).scalar()
    new_7d = conn.execute(sa.select(sa.func.count()).select_from(tender).where(open_cond(), tender.c.first_seen_at > now - timedelta(days=7), *conds)).scalar()
    # La fecha de cierre solo se publica cuando el concurso cierra: lo "reciente" se mide por publicación.
    latest = conn.execute(sa.select(tender.c.ocid).where(open_cond(), *conds)
                          .order_by(tender.c.published_at.desc()).limit(6)).scalars().all()
    prof = build_profile(conn, sids, user["id"])
    recs = recommend_open(conn, prof, k=5, exclude=set(), conds=conds)
    inv_n = conn.execute(sa.select(sa.func.count()).select_from(inventory_item).where(inventory_item.c.org_id == user["org_id"])).scalar()
    inv = inventory_matches(conn, user["org_id"], settings.match_threshold, limit=5, conds=conds) if inv_n else []
    favs = conn.execute(sa.select(sa.func.count()).select_from(favorite).where(favorite.c.user_id == user["id"])).scalar()
    monthly = conn.execute(
        sa.select(sa.func.substr(sa.cast(tender.c.published_at, sa.String), 1, 7).label("m"), sa.func.count())
        .where(*conds).group_by("m").order_by("m")).all()
    top_cls = conn.execute(
        sa.select(tender.c.unspsc_main, sa.func.count().label("n")).where(open_cond(), tender.c.unspsc_main.is_not(None), *conds)
        .group_by(tender.c.unspsc_main).order_by(sa.desc("n")).limit(8)).all()
    won_q = sa.select(sa.func.coalesce(sa.func.sum(award.c.amount), 0)).where(award.c.supplier_id.in_(sids))
    if conds:
        won_q = won_q.where(award.c.ocid.in_(sa.select(tender.c.ocid).where(*conds)))
    won = conn.execute(won_q).scalar() if sids else 0
    return {
        "kpis": {"open": open_total, "new_7d": new_7d, "favorites": favs, "inventory_items": inv_n,
                 "inventory_matches": len(inv), "awarded_total": float(won or 0)},
        "filtered": bool(conds),
        "latest_open": hydrate(conn, [{"ocid": o} for o in latest], user["id"]),
        "closing_soon": [],
        "recommended": hydrate(conn, recs, user["id"]),
        "inventory_matches": hydrate(conn, inv, user["id"]),
        "monthly": [{"month": m, "count": n} for m, n in monthly if m],
        "top_classes": [{"unspsc": c, "count": n} for c, n in top_cls],
    }
