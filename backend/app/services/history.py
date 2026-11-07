"""Historial de una organización en Guatecompras a partir de sus NIT (ofertas y adjudicaciones)."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

import sqlalchemy as sa

from ..models import award, bid, party, tender

IN_PROGRESS = {"active", "planning", "planned"}
VOID = {"unsuccessful", "cancelled", "withdrawn"}
AWARD_VOID = {"cancelled", "unsuccessful", "withdrawn"}


def _iso(v):
    return v.isoformat() + "Z" if hasattr(v, "isoformat") else v


def _rate(won: int, decided: int) -> float | None:
    return round(won / decided, 4) if decided else None


def org_history(conn: sa.Connection, labels: dict[str, str], recent_limit: int = 50) -> dict:
    """Resumen del histórico para los NIT dados ({supplier_id: nombre de identificación})."""
    sids = list(labels)
    names = dict(conn.execute(sa.select(party.c.id, party.c.name).where(party.c.id.in_(sids))).all()) if sids else {}
    by_nit_empty = [{"id": s, "nit": s.replace("GT-NIT-", ""), "label": labels[s], "name": names.get(s),
                     "participated": 0, "won": 0, "decided": 0, "win_rate": None, "awarded_amount": 0.0} for s in sids]
    if not sids:
        return {"has_data": False, "totals": None, "by_nit": [], "monthly": [], "top_buyers": [], "top_classes": [],
                "methods": [], "regions": [], "competitors": [], "recent": {"won": [], "lost": [], "in_progress": []}}

    # ofertas y adjudicaciones propias, por concurso
    my_bids: dict[str, dict[str, float]] = defaultdict(dict)  # ocid -> {sid: monto}
    for ocid, sid, amt in conn.execute(sa.select(bid.c.ocid, bid.c.supplier_id, bid.c.amount).where(bid.c.supplier_id.in_(sids))):
        my_bids[ocid][sid] = my_bids[ocid].get(sid, 0.0) + float(amt or 0)
    my_awards: dict[str, dict[str, float]] = defaultdict(dict)
    for ocid, sid, amt, st in conn.execute(
            sa.select(award.c.ocid, award.c.supplier_id, award.c.amount, award.c.status).where(award.c.supplier_id.in_(sids))):
        if (st or "").lower() in AWARD_VOID:
            continue
        my_awards[ocid][sid] = my_awards[ocid].get(sid, 0.0) + float(amt or 0)

    part_q = sa.union(sa.select(bid.c.ocid).where(bid.c.supplier_id.in_(sids)),
                      sa.select(award.c.ocid).where(award.c.supplier_id.in_(sids))).subquery()
    tenders = {r["ocid"]: dict(r) for r in conn.execute(sa.select(
        tender.c.ocid, tender.c.nog, tender.c.title, tender.c.status, tender.c.status_details, tender.c.method_details,
        tender.c.method, tender.c.published_at, tender.c.buyer_name, tender.c.buyer_region, tender.c.unspsc_main,
        tender.c.n_tenderers).where(tender.c.ocid.in_(sa.select(part_q.c.ocid)))).mappings()}
    if not tenders:
        return {"has_data": False, "totals": None, "by_nit": by_nit_empty, "monthly": [], "top_buyers": [],
                "top_classes": [], "methods": [], "regions": [], "competitors": [],
                "recent": {"won": [], "lost": [], "in_progress": []}}

    def outcome(t: dict) -> str:
        if t["ocid"] in my_awards:
            return "won"
        st = (t["status"] or "").lower()
        if st in IN_PROGRESS:
            return "in_progress"
        if st in VOID:
            return "void"
        return "lost"

    for t in tenders.values():
        t["outcome"] = outcome(t)
        t["awarded_amount"] = sum(my_awards.get(t["ocid"], {}).values())
        t["bid_amount"] = sum(my_bids.get(t["ocid"], {}).values()) or None

    ts = list(tenders.values())
    cnt = Counter(t["outcome"] for t in ts)
    won, lost = cnt["won"], cnt["lost"]
    awarded_amount = sum(t["awarded_amount"] for t in ts)
    dates = [t["published_at"] for t in ts if t["published_at"]]
    comp = [t["n_tenderers"] for t in ts if t["n_tenderers"]]
    won_ts = [t for t in ts if t["outcome"] == "won"]
    bid_amounts = [t["bid_amount"] for t in ts if t["bid_amount"]]

    totals = {
        "participated": len(ts), "won": won, "lost": lost, "in_progress": cnt["in_progress"], "void": cnt["void"],
        "decided": won + lost, "win_rate": _rate(won, won + lost),
        "awarded_amount": awarded_amount, "avg_award": awarded_amount / won if won else None,
        "bid_amount": sum(bid_amounts), "bids_with_amount": len(bid_amounts),
        "buyers_won": len({t["buyer_name"] for t in won_ts if t["buyer_name"]}),
        "buyers_participated": len({t["buyer_name"] for t in ts if t["buyer_name"]}),
        "avg_competitors": round(sum(comp) / len(comp), 1) if comp else None,
        "first_at": _iso(min(dates)) if dates else None, "last_at": _iso(max(dates)) if dates else None,
    }

    # por NIT
    by_nit = []
    for s in sids:
        mine = [t for t in ts if s in my_bids.get(t["ocid"], {}) or s in my_awards.get(t["ocid"], {})]
        w = sum(1 for t in mine if s in my_awards.get(t["ocid"], {}))
        lo = sum(1 for t in mine if t["outcome"] == "lost")
        by_nit.append({"id": s, "nit": s.replace("GT-NIT-", ""), "label": labels[s], "name": names.get(s),
                       "participated": len(mine), "won": w, "decided": w + lo, "win_rate": _rate(w, w + lo),
                       "awarded_amount": sum(my_awards.get(t["ocid"], {}).get(s, 0.0) for t in mine)})

    # agrupaciones
    def group(key, limit: int | None = 8, sort=("won", "participated")):
        g: dict = defaultdict(lambda: {"participated": 0, "won": 0, "lost": 0, "awarded_amount": 0.0})
        for t in ts:
            k = key(t)
            if not k:
                continue
            d = g[k]
            d["participated"] += 1
            d["won"] += t["outcome"] == "won"
            d["lost"] += t["outcome"] == "lost"
            d["awarded_amount"] += t["awarded_amount"]
        rows = [{"key": k, **v, "win_rate": _rate(v["won"], v["won"] + v["lost"])} for k, v in g.items()]
        rows.sort(key=lambda r: tuple(-r[s] for s in sort))
        return rows[:limit] if limit else rows

    monthly = sorted(group(lambda t: t["published_at"].strftime("%Y-%m") if t["published_at"] else None, None),
                     key=lambda r: r["key"])
    top_buyers = group(lambda t: t["buyer_name"])
    top_classes = group(lambda t: t["unspsc_main"])
    sample = {}
    for t in sorted(ts, key=lambda t: t["published_at"] or datetime.min, reverse=True):
        sample.setdefault(t["unspsc_main"], t["title"])
    for c in top_classes:
        c["sample"] = sample.get(c["key"], "")
    methods = group(lambda t: t["method_details"] or t["method"], 6, sort=("participated", "won"))
    regions = group(lambda t: t["buyer_region"], 8, sort=("participated", "won"))

    # competidores que ganaron concursos donde participaste y no ganaste
    lost_ocids = {t["ocid"] for t in ts if t["outcome"] == "lost"}
    comp_c: dict[str, dict] = {}
    if lost_ocids:
        rows = conn.execute(sa.select(award.c.ocid, award.c.supplier_id, award.c.supplier_name, award.c.amount, award.c.status)
                            .where(award.c.ocid.in_(sa.select(bid.c.ocid).where(bid.c.supplier_id.in_(sids))),
                                   award.c.supplier_id.not_in(sids))).all()
        winners_by_ocid: dict[str, list[str]] = defaultdict(list)
        for ocid, sid, name, amt, st in rows:
            if ocid not in lost_ocids or (st or "").lower() in AWARD_VOID or not sid:
                continue
            d = comp_c.setdefault(sid, {"id": sid, "name": name, "n": 0, "amount": 0.0, "_o": set()})
            if ocid not in d["_o"]:
                d["_o"].add(ocid)
                d["n"] += 1
            d["amount"] += float(amt or 0)
            if name not in winners_by_ocid[ocid]:
                winners_by_ocid[ocid].append(name)
        for t in ts:
            t["winners"] = winners_by_ocid.get(t["ocid"], [])
    competitors = sorted(comp_c.values(), key=lambda d: (-d["n"], -d["amount"]))[:8]
    for d in competitors:
        d.pop("_o")

    def item(t: dict) -> dict:
        return {"ocid": t["ocid"], "nog": t["nog"], "title": t["title"], "buyer_name": t["buyer_name"],
                "published_at": _iso(t["published_at"]), "status_details": t["status_details"],
                "method": t["method_details"] or t["method"], "n_tenderers": t["n_tenderers"],
                "awarded_amount": t["awarded_amount"] or None, "bid_amount": t["bid_amount"],
                "winners": t.get("winners", [])}

    recent = {}
    for k in ("won", "lost", "in_progress"):
        sel = sorted((t for t in ts if t["outcome"] == k), key=lambda t: t["published_at"] or datetime.min, reverse=True)
        recent[k] = [item(t) for t in sel[:recent_limit]]

    return {"has_data": True, "totals": totals, "by_nit": by_nit, "monthly": monthly, "top_buyers": top_buyers,
            "top_classes": top_classes, "methods": methods, "regions": regions, "competitors": competitors,
            "recent": recent}
