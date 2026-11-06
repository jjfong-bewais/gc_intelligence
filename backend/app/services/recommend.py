"""Recomendaciones: concursos vigentes parecidos al historial de un proveedor,
ajustados por el feedback (like/dislike) del usuario."""
from __future__ import annotations

from collections import Counter

import numpy as np
import sqlalchemy as sa

from ..db import utcnow
from ..models import award, bid, feedback, inventory_item, tender, tender_item
from .search import open_cond
from .text import unspsc_class
from .vectors import fetch_vectors, vector_search

HALF_LIFE_DAYS = 180.0
MAX_PROFILE = 40


def _decay(age_days: float) -> float:
    return 0.5 ** (max(age_days, 0) / HALF_LIFE_DAYS)


def build_profile(conn: sa.Connection, supplier_ids: list[str], user_id: int | None) -> dict:
    """Perfil = vectores de lo que el proveedor ganó (peso 1), cotizó (0.5) y de lo que gustó."""
    now = utcnow()
    weights: dict[str, tuple[float, str]] = {}  # ocid -> (peso, origen)
    if supplier_ids:
        for ocid, d in conn.execute(
            sa.select(award.c.ocid, sa.func.max(award.c.date)).where(award.c.supplier_id.in_(supplier_ids)).group_by(award.c.ocid)
        ):
            age = (now - d).days if d else 90
            weights[ocid] = (1.0 * _decay(age), "ganó")
        for ocid, d in conn.execute(
            sa.select(bid.c.ocid, sa.func.max(bid.c.date)).where(bid.c.supplier_id.in_(supplier_ids)).group_by(bid.c.ocid)
        ):
            if ocid not in weights:
                age = (now - d).days if d else 90
                weights[ocid] = (0.5 * _decay(age), "cotizó")
    negatives: list[str] = []
    if user_id:
        for ocid, sig in conn.execute(sa.select(feedback.c.ocid, feedback.c.signal).where(feedback.c.user_id == user_id)):
            if sig > 0:
                weights[ocid] = (1.0, "te gustó")
            else:
                negatives.append(ocid)
                weights.pop(ocid, None)
    if not weights:
        return {"vectors": [], "negatives": [], "classes": Counter()}

    vecs = fetch_vectors(conn, tender, tender.c.ocid, list(weights))
    ordered = sorted((o for o in weights if o in vecs), key=lambda o: -weights[o][0])
    kept: list[str] = []
    for o in ordered:  # descarta casi-duplicados para diversificar
        if all(float(vecs[o] @ vecs[x]) < 0.92 for x in kept):
            kept.append(o)
        if len(kept) >= MAX_PROFILE:
            break
    meta = {r[0]: (r[1], r[2], r[3]) for r in conn.execute(
        sa.select(tender.c.ocid, tender.c.title, tender.c.nog, tender.c.unspsc_main).where(tender.c.ocid.in_(list(weights))))}
    classes = Counter(meta[o][2] for o in weights if o in meta and meta[o][2])
    return {
        "vectors": [(vecs[o], weights[o][0], weights[o][1], meta.get(o, ("", 0, ""))) for o in kept],
        "negatives": negatives, "classes": classes,
    }


def recommend_open(
    conn: sa.Connection, profile: dict, k: int = 30, exclude: set[str] | None = None, per_vector: int = 40,
) -> list[dict]:
    """Candidatos vigentes por vecindad con el perfil; el score es la mejor similitud ponderada."""
    exclude = (exclude or set()) | set(profile["negatives"])
    wmax = max((w for _, w, _, _ in profile["vectors"]), default=1.0) or 1.0
    best: dict[str, dict] = {}
    for vec, w, origin, (title, nog, _cls) in profile["vectors"]:
        for ocid, sim in vector_search(conn, tender, tender.c.ocid, vec, per_vector, [open_cond()]):
            if ocid in exclude:
                continue
            score = sim * (0.7 + 0.3 * (w / wmax))
            if ocid not in best or score > best[ocid]["score"]:
                best[ocid] = {"ocid": ocid, "score": score, "sim": sim,
                              "reason": f"Parecido a «{title[:70]}» (NOG {nog}) que {origin}"}
    if not best:
        return []
    ids = list(best)
    classes = {r[0]: r[1] for r in conn.execute(
        sa.select(tender.c.ocid, tender.c.unspsc_main).where(tender.c.ocid.in_(ids)))}
    neg_vecs = fetch_vectors(conn, tender, tender.c.ocid, profile["negatives"]) if profile["negatives"] else {}
    if neg_vecs:
        cand_vecs = fetch_vectors(conn, tender, tender.c.ocid, ids)
        neg = np.stack(list(neg_vecs.values()))
        for o, v in cand_vecs.items():
            pen = float((neg @ v).max())
            best[o]["score"] -= 0.4 * max(0.0, pen - 0.4)  # penaliza vecindad de lo descartado
    for o, c in classes.items():
        if c and profile["classes"].get(c):
            best[o]["score"] += 0.03  # misma clase UNSPSC que su historial
    ranked = sorted(best.values(), key=lambda x: -x["score"])[:k]
    top = ranked[0]["score"] if ranked else 1.0
    for r in ranked:
        r["score"] = round(max(r["score"], 0.0) / (top or 1.0), 3) if top > 0 else 0.0
    return ranked


def inventory_matches(
    conn: sa.Connection, org_id: int, threshold: float, since=None, limit: int = 60, exclude: set[str] | None = None,
) -> list[dict]:
    """Concursos vigentes con ítems que coinciden con productos del inventario."""
    inv = conn.execute(select_inv(org_id)).mappings().all()
    if not inv:
        return []
    conds = [open_cond()]
    if since is not None:
        conds.append(tender.c.first_seen_at > since)
    if exclude:
        conds.append(tender.c.ocid.not_in(list(exclude)))
    open_ids = sa.select(tender.c.ocid).where(*conds)
    by_tender: dict[str, dict] = {}
    for row in inv:
        hits = vector_search(conn, tender_item, tender_item.c.id, row["embedding"], 15, [tender_item.c.ocid.in_(open_ids)])
        if not hits:
            continue
        item_rows = {r["id"]: r for r in conn.execute(
            sa.select(tender_item).where(tender_item.c.id.in_([h[0] for h in hits]))).mappings()}
        for item_id, sim in hits:
            it = item_rows[item_id]
            bonus = 0.08 if row["unspsc"] and unspsc_class(row["unspsc"]) == unspsc_class(it["unspsc"]) else 0.0
            score = sim + bonus
            if score < threshold:
                continue
            d = by_tender.setdefault(it["ocid"], {"ocid": it["ocid"], "score": 0.0, "matches": [], "n_items": 0})
            d["score"] = max(d["score"], score)
            d["matches"].append({
                "inventory_id": row["id"], "sku": row["sku"], "inventory_description": row["description"],
                "item_description": it["description"], "similarity": round(sim, 3),
                "quantity": it["quantity"], "unit": it["unit"],
            })
    out = sorted(by_tender.values(), key=lambda d: -d["score"])[:limit]
    for d in out:
        d["score"] = round(min(d["score"], 1.0), 3)
        d["reason"] = f"{len(d['matches'])} producto(s) de tu inventario coinciden"
    return out


def select_inv(org_id: int):
    return sa.select(inventory_item).where(inventory_item.c.org_id == org_id, inventory_item.c.embedding.is_not(None))
