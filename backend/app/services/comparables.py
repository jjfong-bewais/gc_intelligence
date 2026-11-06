"""Comparables de precio: adjudicaciones pasadas parecidas a un concurso vigente."""
from __future__ import annotations

import statistics
from collections import defaultdict

import numpy as np
import sqlalchemy as sa

from ..config import settings
from ..models import award, price_obs, tender, tender_item
from .search import PORTAL, iso
from .text import unspsc_class
from .vectors import vector_search


def _stats(values: list[float]) -> dict | None:
    if not values:
        return None
    v = sorted(values)
    q = lambda p: float(np.percentile(v, p))  # noqa: E731
    return {
        "n": len(v), "median": float(statistics.median(v)), "p25": q(25), "p75": q(75),
        "min": float(v[0]), "max": float(v[-1]),
    }


def _min_sim() -> float:
    return max(0.25, settings.match_threshold - 0.1)


def price_comparables(conn: sa.Connection, ocid: str, k: int = 60) -> dict:
    t = conn.execute(sa.select(tender).where(tender.c.ocid == ocid)).mappings().first()
    if not t:
        return {"items": [], "similar_tenders": None}
    items = conn.execute(
        sa.select(tender_item).where(tender_item.c.ocid == ocid).order_by(tender_item.c.idx)
    ).mappings().all()
    priced_ids = sa.select(price_obs.c.item_id)
    out_items = []
    for it in items:
        vec = it["embedding"]
        if vec is None:
            out_items.append({"item": _item(it), "stats": None, "comparables": [], "trend": []})
            continue
        base = [tender_item.c.ocid != ocid, tender_item.c.id.in_(priced_ids)]
        cls = unspsc_class(it["unspsc"])
        hits = []
        if cls:
            hits = vector_search(conn, tender_item, tender_item.c.id, vec, k, base + [tender_item.c.unspsc.like(f"{cls}%")])
        hits = [h for h in hits if h[1] >= _min_sim()]
        if len(hits) < 5:  # amplía a otras clases
            more = vector_search(conn, tender_item, tender_item.c.id, vec, k, base)
            seen = {h[0] for h in hits}
            hits += [h for h in more if h[1] >= _min_sim() and h[0] not in seen]
        sims = dict(hits)
        rows = []
        if sims:
            rows = conn.execute(
                sa.select(price_obs, tender.c.nog, tender.c.title, tender.c.buyer_name)
                .join(tender, tender.c.ocid == price_obs.c.ocid)
                .where(price_obs.c.item_id.in_(list(sims)))
            ).mappings().all()
        comps = sorted(rows, key=lambda r: -sims[r["item_id"]])
        by_q: dict[str, list[float]] = defaultdict(list)
        for r in comps:
            if r["awarded_at"]:
                by_q[f"{r['awarded_at'].year}-T{(r['awarded_at'].month - 1) // 3 + 1}"].append(r["unit_price"])
        out_items.append({
            "item": _item(it),
            "stats": _stats([r["unit_price"] for r in comps]),
            "comparables": [{
                "nog": r["nog"], "title": r["title"], "buyer_name": r["buyer_name"],
                "unit_price": r["unit_price"], "quantity": r["quantity"], "unit": r["unit"],
                "supplier": r["supplier_name"], "awarded_at": iso(r["awarded_at"]),
                "similarity": round(sims[r["item_id"]], 3), "portal_url": PORTAL.format(nog=r["nog"]),
            } for r in comps[:15]],
            "trend": [{"period": p, "median": float(statistics.median(v)), "n": len(v)} for p, v in sorted(by_q.items())],
        })

    similar = None
    if t["embedding"] is not None:
        hits = [h for h in vector_search(
            conn, tender, tender.c.ocid, t["embedding"], 40,
            [tender.c.ocid != ocid, tender.c.status == "complete"]) if h[1] >= _min_sim()]
        sims = dict(hits)
        if sims:
            totals = defaultdict(float)
            names: dict[str, str] = {}
            for a in conn.execute(sa.select(award.c.ocid, award.c.amount, award.c.supplier_name).where(award.c.ocid.in_(list(sims)))):
                totals[a[0]] += a[1] or 0
                names[a[0]] = a[2]
            rows = conn.execute(sa.select(tender.c.ocid, tender.c.nog, tender.c.title, tender.c.buyer_name, tender.c.published_at)
                                .where(tender.c.ocid.in_(list(totals)))).all()
            lst = sorted(
                [{"nog": r[1], "title": r[2], "buyer_name": r[3], "published_at": iso(r[4]),
                  "awarded_total": totals[r[0]], "supplier": names[r[0]], "similarity": round(sims[r[0]], 3),
                  "portal_url": PORTAL.format(nog=r[1])} for r in rows],
                key=lambda x: -x["similarity"])
            similar = {"stats": _stats([x["awarded_total"] for x in lst if x["awarded_total"]]), "tenders": lst[:12]}
    return {"items": out_items, "similar_tenders": similar}


def _item(it) -> dict:
    return {"id": it["id"], "description": it["description"], "unspsc": it["unspsc"],
            "quantity": it["quantity"], "unit": it["unit"]}
