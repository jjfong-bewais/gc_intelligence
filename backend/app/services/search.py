"""Búsqueda de concursos: palabras clave, similitud semántica o híbrida (RRF)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import sqlalchemy as sa

from ..db import utcnow
from ..models import award, favorite, feedback, tender, tender_item
from .embeddings import embed_query
from .text import normalize, tokens
from .vectors import vector_search

PORTAL = "https://www.guatecompras.gt/concursos/consultaDetalleCon.aspx?nog={nog}&o=9"


@dataclass
class Filters:
    status: str = "all"  # open | evaluation | awarded | unsuccessful | all
    date_from: date | None = None
    date_to: date | None = None
    unspsc: str = ""
    buyer: str = ""
    method: str = ""
    first_seen_after: datetime | None = None  # para alertas

    @classmethod
    def from_dict(cls, d: dict | None) -> "Filters":
        d = d or {}

        def _d(v):
            return date.fromisoformat(v[:10]) if v else None

        return cls(
            status=d.get("status") or "all", date_from=_d(d.get("date_from")), date_to=_d(d.get("date_to")),
            unspsc=(d.get("unspsc") or "").strip(), buyer=(d.get("buyer") or "").strip(),
            method=(d.get("method") or "").strip(),
        )

    def to_dict(self) -> dict:
        return {
            "status": self.status, "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "unspsc": self.unspsc, "buyer": self.buyer, "method": self.method,
        }


def open_cond():
    return tender.c.status_details == "Vigente"


def build_conds(f: Filters) -> list:
    c = []
    if f.status == "open":
        c.append(open_cond())
    elif f.status == "evaluation":
        c.append(tender.c.status_details == "Evaluación")
    elif f.status == "awarded":
        c.append(tender.c.status == "complete")
    elif f.status == "unsuccessful":
        c.append(tender.c.status == "unsuccessful")
    if f.date_from:
        c.append(tender.c.published_at >= datetime.combine(f.date_from, datetime.min.time()))
    if f.date_to:
        c.append(tender.c.published_at < datetime.combine(f.date_to + timedelta(days=1), datetime.min.time()))
    if f.unspsc:
        c.append(sa.exists().where(
            tender_item.c.ocid == tender.c.ocid, tender_item.c.unspsc.like(f"{f.unspsc}%")
        ))
    if f.buyer:
        c.append(tender.c.buyer_norm.like(f"%{normalize(f.buyer)}%"))
    if f.method:
        c.append(sa.func.lower(tender.c.method_details).like(f"%{f.method.lower()}%"))
    if f.first_seen_after:
        c.append(tender.c.first_seen_at > f.first_seen_after)
    return c


def _keyword(conn, q: str, conds: list, k: int) -> list[tuple[str, float]]:
    toks = tokens(q)
    if not toks:
        return []
    likes = [tender.c.search_text.like(f"%{t}%") for t in toks]
    hits = [sa.case((lk, 1), else_=0) for lk in likes]
    score = hits[0]
    for h in hits[1:]:
        score = score + h
    need = max(1, math.ceil(len(toks) * 0.67)) if len(toks) > 1 else 1
    rows = conn.execute(
        sa.select(tender.c.ocid, score.label("s"))
        .where(sa.or_(*likes), score >= need, *conds)
        .order_by(score.desc(), tender.c.published_at.desc())
        .limit(k)
    ).all()
    return [(r[0], r[1] / len(toks)) for r in rows]


def search_tenders(
    conn: sa.Connection, q: str = "", mode: str = "hybrid", f: Filters | None = None,
    limit: int = 25, offset: int = 0, sort: str = "recent", k: int = 300,
) -> tuple[list[dict], int | None]:
    """Devuelve ([{ocid, score, reason}], total). Sin texto: solo filtros y orden."""
    f = f or Filters()
    conds = build_conds(f)
    q = (q or "").strip()
    if not q:
        total = conn.execute(sa.select(sa.func.count()).select_from(tender).where(*conds)).scalar_one()
        order = tender.c.published_at.desc()
        if sort == "deadline":
            conds = conds + [tender.c.deadline_at.is_not(None)]
            order = tender.c.deadline_at.asc()
        rows = conn.execute(
            sa.select(tender.c.ocid).where(*conds).order_by(order).limit(limit).offset(offset)
        ).all()
        return [{"ocid": r[0], "score": None, "reason": ""} for r in rows], total

    kw = _keyword(conn, q, conds, k) if mode in ("keyword", "hybrid") else []
    sem = vector_search(conn, tender, tender.c.ocid, embed_query(q), k, conds) if mode in ("semantic", "hybrid") else []
    if mode == "keyword":
        merged = {o: {"score": s, "reason": "coincidencia de palabras clave"} for o, s in kw}
    elif mode == "semantic":
        merged = {o: {"score": s, "reason": f"similitud semántica {s:.2f}"} for o, s in sem}
    else:  # RRF
        merged: dict[str, dict] = {}
        for rank, (o, s) in enumerate(kw):
            merged.setdefault(o, {"score": 0.0, "reason": ""})["score"] += 1 / (60 + rank)
            merged[o]["reason"] = "palabras clave"
        for rank, (o, s) in enumerate(sem):
            m = merged.setdefault(o, {"score": 0.0, "reason": ""})
            m["score"] += 1 / (60 + rank)
            m["reason"] = (m["reason"] + " + " if m["reason"] else "") + f"similitud {s:.2f}"
        top = max((m["score"] for m in merged.values()), default=1) or 1
        for m in merged.values():
            m["score"] /= top
    ordered = sorted(merged.items(), key=lambda kv: -kv[1]["score"])
    page = ordered[offset:offset + limit]
    return [{"ocid": o, **m} for o, m in page], len(ordered)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def hydrate(conn: sa.Connection, hits: list[dict], user_id: int | None = None) -> list[dict]:
    """Completa cada resultado con datos del concurso, adjudicación, favorito y feedback."""
    if not hits:
        return []
    ocids = [h["ocid"] for h in hits]
    rows = {
        r["ocid"]: r for r in conn.execute(sa.select(tender).where(tender.c.ocid.in_(ocids))).mappings()
    }
    awards: dict[str, list] = {}
    for a in conn.execute(
        sa.select(award.c.ocid, award.c.amount, award.c.supplier_name, award.c.supplier_id).where(award.c.ocid.in_(ocids))
    ):
        awards.setdefault(a[0], []).append(a)
    favs: dict[str, str] = {}
    fbs: dict[str, int] = {}
    if user_id:
        favs = {r[0]: r[1] for r in conn.execute(
            sa.select(favorite.c.ocid, favorite.c.status).where(favorite.c.user_id == user_id, favorite.c.ocid.in_(ocids)))}
        fbs = {r[0]: r[1] for r in conn.execute(
            sa.select(feedback.c.ocid, feedback.c.signal).where(feedback.c.user_id == user_id, feedback.c.ocid.in_(ocids)))}
    now = utcnow()
    out = []
    for h in hits:
        t = rows.get(h["ocid"])
        if not t:
            continue
        aw = awards.get(h["ocid"], [])
        out.append({
            "ocid": t["ocid"], "nog": t["nog"], "title": t["title"], "status": t["status"],
            "status_details": t["status_details"],
            "is_open": t["status_details"] == "Vigente" and (t["deadline_at"] is None or t["deadline_at"] >= now),
            "method": t["method_details"], "category": t["category"], "buyer_name": t["buyer_name"],
            "unit_name": t["unit_name"], "published_at": iso(t["published_at"]), "deadline_at": iso(t["deadline_at"]),
            "n_tenderers": t["n_tenderers"], "n_items": t["n_items"], "unspsc": t["unspsc_main"],
            "awarded_total": sum(a[1] or 0 for a in aw) if aw else None,
            "winners": sorted({a[2] for a in aw})[:3],
            "favorite": favs.get(t["ocid"]), "feedback": fbs.get(t["ocid"], 0),
            "score": h.get("score"), "reason": h.get("reason", ""),
            "portal_url": PORTAL.format(nog=t["nog"]),
        })
    return out
