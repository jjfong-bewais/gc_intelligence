"""Oportunidades: clases de producto donde participan proveedores semejantes y la
organización no. Semejanza = coseno entre perfiles de clases UNSPSC (TF-IDF)."""
from __future__ import annotations

import math
import time
from collections import defaultdict

import sqlalchemy as sa

from ..models import award, bid, party, tender, tender_item
from .search import open_cond

_CACHE: dict = {"t": 0.0, "data": None}
TTL = 600


def _matrix(conn: sa.Connection) -> dict:
    """supplier -> {clase: participaciones}; clase = UNSPSC (6 dígitos) principal del concurso."""
    if _CACHE["data"] is not None and time.time() - _CACHE["t"] < TTL:
        return _CACHE["data"]
    part = sa.union(
        sa.select(bid.c.supplier_id.label("sid"), bid.c.ocid.label("ocid")).where(bid.c.supplier_id.is_not(None)),
        sa.select(award.c.supplier_id.label("sid"), award.c.ocid.label("ocid")).where(award.c.supplier_id.is_not(None)),
    ).subquery()
    rows = conn.execute(
        sa.select(part.c.sid, tender.c.unspsc_main, sa.func.count())
        .select_from(part.join(tender, tender.c.ocid == part.c.ocid))
        .where(tender.c.unspsc_main.is_not(None))
        .group_by(part.c.sid, tender.c.unspsc_main)
    ).all()
    m: dict[str, dict[str, int]] = defaultdict(dict)
    for sid, cls, n in rows:
        m[sid][cls] = n
    amounts: dict[tuple[str, str], float] = defaultdict(float)
    for sid, cls, amt in conn.execute(
        sa.select(award.c.supplier_id, tender.c.unspsc_main, sa.func.sum(award.c.amount))
        .select_from(award.join(tender, tender.c.ocid == award.c.ocid))
        .where(tender.c.unspsc_main.is_not(None)).group_by(award.c.supplier_id, tender.c.unspsc_main)
    ):
        amounts[(sid, cls)] = amt or 0.0
    df: dict[str, int] = defaultdict(int)
    for cs in m.values():
        for c in cs:
            df[c] += 1
    n_sup = max(len(m), 1)
    idf = {c: math.log(1 + n_sup / (1 + d)) for c, d in df.items()}
    data = {"m": m, "idf": idf, "amounts": amounts}
    _CACHE.update(t=time.time(), data=data)
    return data


def clear_cache() -> None:
    _CACHE.update(t=0.0, data=None)


def _vec(counts: dict[str, int], idf: dict[str, float]) -> dict[str, float]:
    v = {c: (1 + math.log(n)) * idf.get(c, 1.0) for c, n in counts.items() if n > 0}
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {c: x / norm for c, x in v.items()}


def _merge(counts_list: list[dict[str, int]]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for cs in counts_list:
        for c, n in cs.items():
            out[c] += n
    return out


def find_peers(conn: sa.Connection, supplier_ids: list[str], n_peers: int = 25, min_part: int = 3) -> list[dict]:
    data = _matrix(conn)
    own = _merge([data["m"].get(s, {}) for s in supplier_ids])
    if not own:
        return []
    ov = _vec(own, data["idf"])
    scored = []
    for sid, cs in data["m"].items():
        if sid in supplier_ids or sum(cs.values()) < min_part:
            continue
        v = _vec(cs, data["idf"])
        sim = sum(w * v.get(c, 0.0) for c, w in ov.items())
        if sim > 0.1:
            shared = sorted((c for c in cs if c in own), key=lambda c: -cs[c])
            scored.append({"id": sid, "similarity": round(sim, 3), "participations": sum(cs.values()), "shared_classes": shared[:5]})
    scored.sort(key=lambda x: -x["similarity"])
    top = scored[:n_peers]
    names = {r[0]: r[1] for r in conn.execute(sa.select(party.c.id, party.c.name).where(party.c.id.in_([p["id"] for p in top])))}
    for p in top:
        p["name"] = names.get(p["id"], p["id"])
    return top


def _examples(conn: sa.Connection, cls: str, n: int = 3) -> list[str]:
    rows = conn.execute(
        sa.select(tender_item.c.description, sa.func.count().label("c"))
        .where(tender_item.c.unspsc.like(f"{cls}%"))
        .group_by(tender_item.c.description).order_by(sa.desc("c")).limit(n)
    ).all()
    return [r[0] for r in rows]


def opportunities(conn: sa.Connection, supplier_ids: list[str], limit: int = 30, n_peers: int = 25) -> dict:
    data = _matrix(conn)
    own = _merge([data["m"].get(s, {}) for s in supplier_ids])
    peers = find_peers(conn, supplier_ids, n_peers)
    if not peers:
        return {"peers": [], "opportunities": [], "own_classes": len(own)}
    agg: dict[str, dict] = {}
    for p in peers:
        for cls, n in data["m"][p["id"]].items():
            if own.get(cls):
                continue
            a = agg.setdefault(cls, {"cls": cls, "n_peers": 0, "peer_participations": 0, "weight": 0.0,
                                     "peer_awarded": 0.0, "peers": []})
            a["n_peers"] += 1
            a["peer_participations"] += n
            a["weight"] += p["similarity"] * math.log(1 + n)
            a["peer_awarded"] += data["amounts"].get((p["id"], cls), 0.0)
            a["peers"].append(p["name"])
    ranked = sorted((a for a in agg.values() if a["n_peers"] >= 2), key=lambda a: -a["weight"])[:limit]
    open_by_cls = {r[0]: r[1] for r in conn.execute(
        sa.select(tender.c.unspsc_main, sa.func.count()).where(open_cond(), tender.c.unspsc_main.in_([a["cls"] for a in ranked]))
        .group_by(tender.c.unspsc_main))}
    out = []
    for a in ranked:
        ex = _examples(conn, a["cls"])
        out.append({
            "unspsc_class": a["cls"], "label": ex[0].title() if ex else a["cls"], "examples": ex,
            "n_peers": a["n_peers"], "peer_participations": a["peer_participations"],
            "peer_awarded_amount": round(a["peer_awarded"], 2), "open_now": open_by_cls.get(a["cls"], 0),
            "top_peers": a["peers"][:3], "score": round(a["weight"], 3),
        })
    return {"peers": peers[:10], "opportunities": out, "own_classes": len(own)}
