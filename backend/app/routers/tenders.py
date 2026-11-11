from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from ..db import get_conn
from ..models import award, bid, contract, document, favorite, feedback, tender, tender_item
from ..permissions import Perm, require
from ..services import usage
from ..services.comparables import price_comparables
from ..services.search import Filters, hydrate, iso, search_tenders
from ..services.vectors import vector_search

router = APIRouter(prefix="/tenders", tags=["tenders"])


class SearchBody(BaseModel):
    q: str = ""
    mode: str = "hybrid"
    filters: dict = {}
    sort: str = "recent"
    limit: int = 25
    offset: int = 0


@router.post("/search")
def search(body: SearchBody, request: Request, user=Depends(require(Perm.SEARCH)), conn=Depends(get_conn)):
    hits, total = search_tenders(conn, body.q, body.mode, Filters.from_dict(body.filters),
                                 min(body.limit, 100), body.offset, body.sort)
    usage.note(request, q=body.q.strip()[:300], mode=body.mode, sort=body.sort, offset=body.offset, total=total,
               filters={k: v for k, v in body.filters.items() if v not in (None, "", [], {}, False)},
               used_embedding=bool(body.q.strip()) and body.mode in ("semantic", "hybrid"))
    return {"total": total, "items": hydrate(conn, hits, user["id"])}


def _by_nog(conn, nog: int) -> str:
    ocid = conn.execute(sa.select(tender.c.ocid).where(tender.c.nog == nog)).scalar()
    if not ocid:
        raise HTTPException(404, "Concurso no encontrado")
    return ocid


@router.get("/{nog}")
def detail(nog: int, request: Request, user=Depends(require(Perm.SEARCH)), conn=Depends(get_conn)):
    ocid = _by_nog(conn, nog)
    usage.note(request, nog=nog)
    base = hydrate(conn, [{"ocid": ocid}], user["id"])[0]
    items = conn.execute(sa.select(tender_item).where(tender_item.c.ocid == ocid).order_by(tender_item.c.idx)).mappings().all()
    return {
        **base,
        "items": [{"id": i["id"], "description": i["description"], "unspsc": i["unspsc"],
                   "quantity": i["quantity"], "unit": i["unit"]} for i in items],
        "bids": [dict(r) | {"date": iso(r.get("date"))} for r in conn.execute(
            sa.select(bid.c.supplier_id, bid.c.supplier_name, bid.c.amount, bid.c.status, bid.c.date).where(bid.c.ocid == ocid)).mappings()],
        "awards": [dict(r) | {"date": iso(r.get("date"))} for r in conn.execute(
            sa.select(award.c.supplier_id, award.c.supplier_name, award.c.amount, award.c.status_details, award.c.date).where(award.c.ocid == ocid)).mappings()],
        "contracts": [dict(r) for r in conn.execute(sa.select(contract.c.number, contract.c.amount).where(contract.c.ocid == ocid)).mappings()],
        "documents": [dict(r) for r in conn.execute(sa.select(document.c.doc_type, document.c.title, document.c.url).where(document.c.ocid == ocid)).mappings()],
    }


@router.get("/{nog}/similar")
def similar(nog: int, status: str = Query("awarded"), limit: int = 12, user=Depends(require(Perm.SEARCH)), conn=Depends(get_conn)):
    ocid = _by_nog(conn, nog)
    vec = conn.execute(sa.select(tender.c.embedding).where(tender.c.ocid == ocid)).scalar()
    if vec is None:
        return {"items": []}
    conds = [tender.c.ocid != ocid]
    f = Filters(status=status if status in ("open", "awarded", "evaluation", "unsuccessful") else "all")
    from ..services.search import build_conds
    hits = vector_search(conn, tender, tender.c.ocid, vec, limit, conds + build_conds(f))
    return {"items": hydrate(conn, [{"ocid": o, "score": s, "reason": f"similitud {s:.2f}"} for o, s in hits], user["id"])}


@router.get("/{nog}/price-comparables")
def comparables(nog: int, user=Depends(require(Perm.SEARCH)), conn=Depends(get_conn)):
    return price_comparables(conn, _by_nog(conn, nog))
