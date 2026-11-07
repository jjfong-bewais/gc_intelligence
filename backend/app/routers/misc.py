from __future__ import annotations

import time

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from ..config import settings
from ..db import get_conn
from ..models import ingest_file, saved_search, tender, tender_item, party
from ..security import admin_user, current_user, read_link
from ..services.alerts import run_all
from ..services.embeddings import embed_pending
from ..services.search import FACET_COLUMNS, NONE_VALUE, open_cond
from ..services.text import normalize
from .workspace import save_feedback

router = APIRouter(tags=["misc"])


@router.get("/health")
def health(conn=Depends(get_conn)):
    conn.execute(sa.text("select 1"))
    return {"ok": True, "mode": settings.gc_mode}


@router.get("/catalogs/classes")
def classes(user=Depends(current_user), conn=Depends(get_conn)):
    rows = conn.execute(
        sa.select(sa.func.substr(tender_item.c.unspsc, 1, 6).label("c"), sa.func.min(tender_item.c.description), sa.func.count().label("n"))
        .where(tender_item.c.unspsc != "").group_by("c").order_by(sa.desc("n")).limit(200)).all()
    return {"items": [{"code": c, "label": (d or "")[:60], "count": n} for c, d, n in rows]}


_FACETS_CACHE: dict = {"t": 0.0, "data": None}
FACETS_TTL = 900


@router.get("/catalogs/facets")
def facets(user=Depends(current_user), conn=Depends(get_conn)):
    """Valores posibles (y conteo total) de cada filtro de selección múltiple. Caché 15 min."""
    if _FACETS_CACHE["data"] is not None and time.time() - _FACETS_CACHE["t"] < FACETS_TTL:
        return _FACETS_CACHE["data"]
    out = {}
    for key, col in FACET_COLUMNS.items():
        rows = conn.execute(sa.select(col, sa.func.count().label("n")).group_by(col).order_by(sa.desc("n")).limit(300)).all()
        out[key] = [{"value": v if v is not None else NONE_VALUE, "count": n} for v, n in rows]
    _FACETS_CACHE.update(t=time.time(), data=out)
    return out


@router.get("/catalogs/buyers")
def buyers(q: str = "", user=Depends(current_user), conn=Depends(get_conn)):
    stmt = sa.select(tender.c.buyer_name, sa.func.count().label("n")).where(tender.c.buyer_name != "")
    if q.strip():
        stmt = stmt.where(tender.c.buyer_norm.like(f"%{normalize(q)}%"))
    rows = conn.execute(stmt.group_by(tender.c.buyer_name).order_by(sa.desc("n")).limit(20)).all()
    return {"items": [{"name": n, "count": c} for n, c in rows]}


@router.get("/admin/status")
def status(user=Depends(admin_user), conn=Depends(get_conn)):
    files = conn.execute(sa.select(ingest_file).order_by(ingest_file.c.key)).mappings().all()
    return {
        "tenders": conn.execute(sa.select(sa.func.count()).select_from(tender)).scalar(),
        "open": conn.execute(sa.select(sa.func.count()).select_from(tender).where(open_cond())).scalar(),
        "without_embedding": conn.execute(sa.select(sa.func.count()).select_from(tender).where(tender.c.embedding.is_(None))).scalar(),
        "files": [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(f).items()} for f in files],
        "embeddings": settings.embeddings_provider, "mail": settings.mail_provider, "mode": settings.gc_mode,
    }


@router.post("/admin/alerts/run")
def admin_alerts(user=Depends(admin_user), conn=Depends(get_conn)):
    return run_all(conn, force=True)


@router.post("/admin/embed")
def admin_embed(user=Depends(admin_user), conn=Depends(get_conn)):
    return embed_pending(conn)


def _page(msg: str) -> HTMLResponse:
    return HTMLResponse(f'<meta charset="utf-8"><body style="font-family:system-ui;max-width:480px;margin:15vh auto;text-align:center">'
                        f'<h3>{msg}</h3><p><a href="{settings.app_url}">Ir a la plataforma</a></p></body>')


@router.get("/links/{kind}", include_in_schema=False)
def link(kind: str, t: str, conn=Depends(get_conn)):
    p = read_link(t)
    if not p or p.get("k") != kind:
        return _page("Enlace inválido o vencido")
    if kind == "feedback":
        save_feedback(conn, int(p["u"]), p["o"], int(p["s"]), context=p.get("c", "email"))
        return _page("¡Gracias! Registramos tu opinión." if int(p["s"]) > 0 else "Anotado: te mostraremos menos como este.")
    if kind == "unsubscribe":
        conn.execute(sa.update(saved_search).where(saved_search.c.id == int(p["s"])).values(active=False))
        return _page("Alerta pausada. Puedes reactivarla en la plataforma.")
    return _page("Enlace inválido")
