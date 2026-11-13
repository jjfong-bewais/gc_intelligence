"""Búsqueda de concursos: palabras clave, similitud semántica o híbrida (RRF)."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import sqlalchemy as sa

from ..db import utcnow
from ..models import award, favorite, feedback, tender, tender_item
from .embeddings import embed_query
from .text import normalize, tokens
from .vectors import vector_search

PORTAL = "https://www.guatecompras.gt/concursos/consultaDetalleCon.aspx?nog={nog}&o=9"


# Facetas de selección múltiple sobre columnas del concurso (clave en el JSON -> columna).
FACET_COLUMNS = {
    "category": tender.c.category,  # goods | services | works
    "status_details": tender.c.status_details,  # Vigente | Evaluación | Adjudicado | Desierto…
    "department": tender.c.buyer_region,
    "entity_type": tender.c.buyer_type,
    "method": tender.c.method_details,
}
TEXT_FACETS = ("buyer", "supplier")  # entidad (texto) y proveedor adjudicado (NIT)
NONE_VALUE = "__none__"  # "sin dato" en facetas
DATE_PRESETS = {"7d": 7, "30d": 30, "3m": 91, "6m": 182, "1y": 365}
GT_OFFSET = timedelta(hours=-6)  # Guatemala no usa horario de verano


@dataclass
class Sel:
    """Selección de una faceta: `in` delimita a los valores, `out` los excluye."""
    op: str = "in"
    values: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, v) -> "Sel | None":
        if isinstance(v, str):  # formato anterior: texto libre = incluir
            return cls("in", [v.strip()]) if v.strip() else None
        if isinstance(v, list):
            v = {"op": "in", "values": v}
        if not isinstance(v, dict):
            return None
        vals = [str(x).strip() for x in (v.get("values") or []) if str(x).strip()]
        if not vals:
            return None
        return cls("out" if v.get("op") in ("out", "exclude", "not_in") else "in", vals[:200])


@dataclass
class Filters:
    status: str = "all"  # (anterior) open | evaluation | awarded | unsuccessful | all
    date_from: date | None = None
    date_to: date | None = None
    date_preset: str = ""  # 7d | 30d | 3m | 6m | 1y (relativo a hoy; útil en alertas)
    unspsc: str = ""
    open_only: bool = False  # recepción de ofertas abierta
    awarded_only: bool = False
    sel: dict[str, Sel] = field(default_factory=dict)
    first_seen_after: datetime | None = None  # para alertas

    @classmethod
    def from_dict(cls, d: dict | None) -> "Filters":
        d = d or {}

        def _d(v):
            try:
                return date.fromisoformat(str(v)[:10]) if v else None
            except ValueError:
                return None

        sel = {}
        for key in (*FACET_COLUMNS, *TEXT_FACETS):
            v = Sel.parse(d.get(key))
            if v:
                sel[key] = v
        if isinstance(d.get("method"), str) and "method" in sel:  # anterior: subcadena
            sel["method_text"] = sel.pop("method")
        status = d.get("status") if isinstance(d.get("status"), str) else "all"
        return cls(
            status=status or "all", date_from=_d(d.get("date_from")), date_to=_d(d.get("date_to")),
            date_preset=d.get("date_preset") if d.get("date_preset") in DATE_PRESETS else "",
            unspsc=(d.get("unspsc") or "").strip() if isinstance(d.get("unspsc"), str) else "",
            open_only=bool(d.get("open_only")), awarded_only=bool(d.get("awarded_only")), sel=sel,
        )

    def to_dict(self) -> dict:
        out = {
            "status": self.status, "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None, "date_preset": self.date_preset or None,
            "unspsc": self.unspsc, "open_only": self.open_only, "awarded_only": self.awarded_only,
        }
        for k, v in self.sel.items():
            out[k] = {"op": v.op, "values": v.values}
        return out

    def key(self) -> str:
        """Clave estable para cachés."""
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)

    def is_empty(self) -> bool:
        return Filters.from_dict({}).key() == self.key()


def parse_filters_param(raw: str | None) -> Filters:
    """Filtros enviados como JSON en un parámetro de URL (?f=...)."""
    if not raw:
        return Filters()
    try:
        d = json.loads(raw)
    except ValueError:
        return Filters()
    return Filters.from_dict(d if isinstance(d, dict) else {})


def open_cond():
    return tender.c.status_details == "Vigente"


def accepting_cond(now: datetime | None = None):
    """Vigente y con recepción de ofertas abierta (sin fecha de cierre o cierre futuro)."""
    now = now or utcnow()
    return sa.and_(open_cond(), sa.or_(tender.c.deadline_at.is_(None), tender.c.deadline_at >= now))


def _in_values(col, s: Sel):
    vals = [v for v in s.values if v != NONE_VALUE]
    parts = []
    if vals:
        parts.append(col.in_(vals))
    if NONE_VALUE in s.values:
        parts.append(col.is_(None))
    cond = sa.or_(*parts)
    if s.op == "in":
        return cond
    return sa.or_(col.is_(None), sa.not_(cond)) if NONE_VALUE not in s.values else sa.not_(cond)


def _buyer_cond(s: Sel):
    parts = []
    for v in s.values:
        n = normalize(v)
        p = [sa.func.lower(tender.c.unit_name).like(f"%{v.lower()}%")]
        if n:
            p.append(tender.c.buyer_norm.like(f"%{n}%"))
        parts.append(sa.or_(*p))
    cond = sa.or_(*parts)
    return cond if s.op == "in" else sa.not_(cond)


def _supplier_cond(s: Sel):
    ids = [v if v.startswith("GT-") else f"GT-NIT-{v}" for v in s.values]
    ex = sa.exists().where(award.c.ocid == tender.c.ocid, award.c.supplier_id.in_(ids))
    return ex if s.op == "in" else sa.not_(ex)


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
    if f.open_only:
        c.append(accepting_cond())
    if f.awarded_only:
        c.append(tender.c.status == "complete")
    date_from = f.date_from
    if f.date_preset:
        today_gt = (utcnow() + GT_OFFSET).date()
        date_from = today_gt - timedelta(days=DATE_PRESETS[f.date_preset])
    if date_from:  # fechas de Guatemala -> UTC
        c.append(tender.c.published_at >= datetime.combine(date_from, datetime.min.time()) - GT_OFFSET)
    if f.date_to and not f.date_preset:
        c.append(tender.c.published_at < datetime.combine(f.date_to + timedelta(days=1), datetime.min.time()) - GT_OFFSET)
    if f.unspsc:
        c.append(sa.exists().where(
            tender_item.c.ocid == tender.c.ocid, tender_item.c.unspsc.like(f"{f.unspsc}%")
        ))
    for key, col in FACET_COLUMNS.items():
        if key in f.sel:
            c.append(_in_values(col, f.sel[key]))
    if "method_text" in f.sel:
        c.append(sa.func.lower(tender.c.method_details).like(f"%{f.sel['method_text'].values[0].lower()}%"))
    if "buyer" in f.sel:
        c.append(_buyer_cond(f.sel["buyer"]))
    if "supplier" in f.sel:
        c.append(_supplier_cond(f.sel["supplier"]))
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
    limit: int = 25, offset: int = 0, sort: str = "recent", k: int = 300, extra_conds: list | None = None,
) -> tuple[list[dict], int | None]:
    """Devuelve ([{ocid, score, reason}], total). Sin texto: solo filtros y orden.
    `extra_conds` reemplaza a los filtros de `f` si se indica (ya construidos)."""
    f = f or Filters()
    conds = list(extra_conds) if extra_conds is not None else build_conds(f)
    q = (q or "").strip()
    if not q:
        order = tender.c.published_at.desc()
        if sort == "oldest":  # los que llevan más tiempo abiertos (la fecha de cierre aún no existe)
            order = tender.c.published_at.asc()
        elif sort == "deadline":
            conds = conds + [tender.c.deadline_at.is_not(None)]
            order = tender.c.deadline_at.asc()
        total = conn.execute(sa.select(sa.func.count()).select_from(tender).where(*conds)).scalar_one()
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


MIN_REFERENCE = 5  # adjudicaciones mínimas para mostrar un precio de referencia


def class_reference(conn: sa.Connection, classes: set[str]) -> dict[str, dict]:
    """Mediana de adjudicación y oferentes típicos por clase UNSPSC (6 dígitos).
    Solo incluye clases con al menos MIN_REFERENCE adjudicaciones."""
    import statistics
    out: dict[str, dict] = {}
    for cls in {c for c in classes if c}:
        rows = conn.execute(
            sa.select(sa.func.sum(award.c.amount), tender.c.n_tenderers)
            .select_from(award.join(tender, tender.c.ocid == award.c.ocid))
            .where(tender.c.unspsc_main.like(f"{cls}%"), award.c.amount.is_not(None), award.c.amount > 0,
                   sa.func.lower(sa.func.coalesce(award.c.status, "")).not_in(("cancelled", "unsuccessful", "withdrawn")))
            .group_by(award.c.ocid, tender.c.n_tenderers).limit(500)).all()
        if len(rows) < MIN_REFERENCE:
            continue
        amounts = [float(r[0]) for r in rows]
        bidders = [r[1] for r in rows if r[1]]
        out[cls] = {"median": float(statistics.median(amounts)), "n": len(amounts),
                    "typical_bidders": round(sum(bidders) / len(bidders), 1) if bidders else None}
    return out


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
    my_prices: dict[str, float | None] = {}
    fbs: dict[str, int] = {}
    if user_id:
        favs = {r[0]: r[1] for r in conn.execute(
            sa.select(favorite.c.ocid, favorite.c.status).where(favorite.c.user_id == user_id, favorite.c.ocid.in_(ocids)))}
        my_prices = {r[0]: r[1] for r in conn.execute(
            sa.select(favorite.c.ocid, favorite.c.my_price).where(favorite.c.user_id == user_id, favorite.c.ocid.in_(ocids)))}
        fbs = {r[0]: r[1] for r in conn.execute(
            sa.select(feedback.c.ocid, feedback.c.signal).where(feedback.c.user_id == user_id, feedback.c.ocid.in_(ocids)))}
    now = utcnow()
    refs = class_reference(conn, {(t["unspsc_main"] or "")[:6] for t in rows.values()})
    out = []
    for h in hits:
        t = rows.get(h["ocid"])
        if not t:
            continue
        aw = awards.get(h["ocid"], [])
        ref = refs.get((t["unspsc_main"] or "")[:6])
        pub = t["published_at"]
        out.append({
            "ocid": t["ocid"], "nog": t["nog"], "title": t["title"], "status": t["status"],
            "status_details": t["status_details"],
            "is_open": t["status_details"] == "Vigente" and (t["deadline_at"] is None or t["deadline_at"] >= now),
            "method": t["method_details"], "category": t["category"], "buyer_name": t["buyer_name"],
            "unit_name": t["unit_name"], "department": t["buyer_region"], "entity_type": t["buyer_type"],
            "published_at": iso(t["published_at"]), "deadline_at": iso(t["deadline_at"]),
            "n_tenderers": t["n_tenderers"], "n_items": t["n_items"], "unspsc": t["unspsc_main"],
            "awarded_total": sum(a[1] or 0 for a in aw) if aw else None,
            "winners": sorted({a[2] for a in aw})[:3],
            "days_since_published": (now - pub).days if pub else None,
            "reference_price": ref["median"] if ref else None, "reference_n": ref["n"] if ref else 0,
            "typical_bidders": ref["typical_bidders"] if ref else None,
            "my_price": my_prices.get(t["ocid"]),
            "favorite": favs.get(t["ocid"]), "feedback": fbs.get(t["ocid"], 0),
            "score": h.get("score"), "reason": h.get("reason", ""),
            "portal_url": PORTAL.format(nog=t["nog"]),
        })
    return out
