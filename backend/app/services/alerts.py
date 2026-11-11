"""Alertas por correo: combinaciones de filtros guardadas (mejores 1-10 concursos vigentes por
usuario, sin repetir en 7 días) e inventario (idempotente por inventory_alert)."""
from __future__ import annotations

from datetime import timedelta
from html import escape

import sqlalchemy as sa

from ..config import settings
from ..db import utcnow
from ..models import alert_sent, app_user, favorite, inventory_alert, org_supplier, saved_search, tender
from ..security import make_link
from .mailer import send_email
from .recommend import build_profile, inventory_matches, profile_scores, recommend_open
from .search import Filters, accepting_cond, build_conds, hydrate, search_tenders

FREQ = {"immediate": timedelta(minutes=0), "daily": timedelta(hours=23), "weekly": timedelta(days=6, hours=23)}
MAX_PER_MAIL = 25  # alertas de inventario
MIN_ITEMS, MAX_ITEMS = 1, 10  # concursos por correo de una combinación guardada
REPEAT_WINDOW = timedelta(days=7)  # no repetir un concurso al mismo usuario en este plazo


def _link(kind: str, **p) -> str:
    return f"{settings.public_api_url}/api/v1/links/{kind}?t={make_link({'k': kind, **p})}"


def _card(h: dict, user_id: int, ctx: str) -> str:
    fb = lambda s: _link("feedback", u=user_id, o=h["ocid"], s=s, c=ctx)  # noqa: E731
    dl = (h["deadline_at"] or "")[:10]
    return (
        f'<div style="border:1px solid #e2e8f0;border-radius:8px;padding:12px;margin:10px 0">'
        f'<div style="font-weight:600">{escape(h["title"][:140])}</div>'
        f'<div style="color:#64748b;font-size:13px">NOG {h["nog"]} · {escape(h["buyer_name"][:80])}'
        f'{" · cierra " + dl if dl else ""}</div>'
        + (f'<div style="font-size:13px;margin-top:4px">{escape(h["reason"])}</div>' if h.get("reason") else "")
        + f'<div style="margin-top:8px;font-size:13px"><a href="{settings.app_url}/tenders/{h["ocid"]}?src=alert">Ver en la plataforma</a>'
        f' · <a href="{h["portal_url"]}">Guatecompras</a> · <a href="{fb(1)}">👍</a> <a href="{fb(-1)}">👎</a></div></div>'
    )


def _mail(title: str, intro: str, cards: list[str], unsub: str) -> str:
    return (
        '<div style="font-family:system-ui,sans-serif;max-width:640px;margin:auto">'
        f'<h2>{escape(title)}</h2><p>{escape(intro)}</p>{"".join(cards)}'
        f'<p style="color:#94a3b8;font-size:12px"><a href="{unsub}">Pausar esta alerta</a></p></div>'
    )


def _due(s, now) -> bool:
    return s["last_run_at"] is None or now - s["last_run_at"] >= FREQ.get(s["frequency"], FREQ["daily"])


def pick_for_saved(conn: sa.Connection, s: dict, profile: dict, exclude: set[str], now) -> list[dict]:
    """Los 1-10 concursos vigentes (recibiendo ofertas) que cumplen la combinación de filtros
    y mejor coinciden con el usuario. Sin texto: afinidad con el perfil (o los más recientes).
    Con texto: relevancia de la búsqueda combinada con la afinidad."""
    n = max(MIN_ITEMS, min(MAX_ITEMS, int(s.get("max_items") or 5)))
    f = Filters.from_dict(s["filters"])
    conds = [accepting_cond(now), *build_conds(f)]
    if exclude and len(exclude) <= 2000:
        conds.append(tender.c.ocid.not_in(list(exclude)))
    pool: dict[str, dict] = {}
    q = (s.get("q") or "").strip()
    if q:
        hits, _ = search_tenders(conn, q, s.get("mode") or "hybrid", f, limit=200, extra_conds=conds)
        for h in hits:
            pool[h["ocid"]] = {"ocid": h["ocid"], "search": h["score"] or 0.0, "reason": "Coincide con tu búsqueda"}
    else:
        if profile["vectors"]:
            for r in recommend_open(conn, profile, k=100, per_vector=25, conds=conds[1:], base=conds[0]):
                pool[r["ocid"]] = {"ocid": r["ocid"], "search": 0.0, "reason": r["reason"]}
        recent = conn.execute(sa.select(tender.c.ocid).where(*conds)
                              .order_by(tender.c.published_at.desc()).limit(200)).scalars().all()
        for i, o in enumerate(recent):
            pool.setdefault(o, {"ocid": o, "search": 0.0, "reason": "Publicado recientemente"})
            pool[o]["recency"] = 1.0 - i / max(len(recent), 1)
    pool = {o: v for o, v in pool.items() if o not in exclude}
    if not pool:
        return []
    aff = profile_scores(conn, profile, list(pool))
    for o, c in pool.items():
        a = aff.get(o)
        if a:
            c["score"] = (0.6 * a["score"] + 0.4 * c["search"]) if q else a["score"]
            if not q or a["sim"] >= 0.5:
                c["reason"] = a["reason"]
        else:
            c["score"] = c["search"] if q else 0.2 * c.get("recency", 0.0)
    ranked = sorted(pool.values(), key=lambda c: -c["score"])[:n]
    top = ranked[0]["score"] or 1.0
    for c in ranked:
        c["score"] = round(max(c["score"], 0.0) / top, 3) if top > 0 else None
    return ranked


def run_saved_searches(conn: sa.Connection, force: bool = False, user_id: int | None = None) -> dict:
    """Envía por cada combinación guardada activa un correo con sus mejores 1-10 concursos vigentes.
    Un concurso enviado a un usuario no se le vuelve a enviar en los siguientes 7 días
    (tampoco desde otra combinación) ni se envían los que marcó 👎 o ya sigue."""
    now = utcnow()
    sent = mails = 0
    stmt = (sa.select(saved_search, app_user.c.email, app_user.c.org_id).join(app_user, app_user.c.id == saved_search.c.user_id)
            .where(saved_search.c.active.is_(True), app_user.c.active.is_(True)).order_by(saved_search.c.user_id, saved_search.c.id))
    if user_id is not None:
        stmt = stmt.where(saved_search.c.user_id == user_id)
    rows = conn.execute(stmt).mappings().all()
    profiles: dict[int, dict] = {}
    excluded: dict[int, set[str]] = {}
    for s in rows:
        if not force and not _due(s, now):
            continue
        uid = s["user_id"]
        if uid not in profiles:
            sids = list(conn.execute(sa.select(org_supplier.c.supplier_id).where(org_supplier.c.org_id == s["org_id"])).scalars())
            profiles[uid] = build_profile(conn, sids, uid)
            ex = set(conn.execute(sa.select(alert_sent.c.ocid).where(
                alert_sent.c.user_id == uid, alert_sent.c.sent_at > now - REPEAT_WINDOW)).scalars())
            ex |= set(conn.execute(sa.select(favorite.c.ocid).where(favorite.c.user_id == uid)).scalars())
            ex |= set(profiles[uid]["negatives"])
            excluded[uid] = ex
        picks = pick_for_saved(conn, dict(s), profiles[uid], excluded[uid], now)
        if picks:
            meta = {h["ocid"]: h for h in hydrate(conn, picks, uid)}
            cards = [_card(dict(meta[p["ocid"]], reason=p["reason"]), uid, "alert") for p in picks if p["ocid"] in meta]
            intro = (f"Los {len(cards)} concursos vigentes que mejor coinciden contigo y con tu combinación de filtros. "
                     "No repetimos concursos enviados en los últimos 7 días.")
            html = _mail(f"{s['name']}", intro, cards, _link("unsubscribe", s=s["id"]))
            if not send_email(s["email"], f"[GC] {len(cards)} concurso(s) para ti: {s['name']}", html):
                continue  # no avanzar last_run_at si el envío falló
            conn.execute(sa.insert(alert_sent), [
                {"user_id": uid, "ocid": p["ocid"], "saved_search_id": s["id"], "sent_at": now} for p in picks])
            excluded[uid] |= {p["ocid"] for p in picks}
            sent += len(picks)
            mails += 1
        conn.execute(sa.update(saved_search).where(saved_search.c.id == s["id"]).values(last_run_at=now))
    return {"mails": mails, "tenders": sent}


def run_inventory_alerts(conn: sa.Connection) -> dict:
    now = utcnow()
    mails = n = 0
    orgs = conn.execute(sa.select(app_user.c.org_id).where(app_user.c.active.is_(True)).distinct()).scalars().all()
    for org in orgs:
        done = {r[0] for r in conn.execute(sa.select(inventory_alert.c.ocid).where(inventory_alert.c.org_id == org))}
        found = inventory_matches(conn, org, settings.match_threshold, since=now - timedelta(days=3), exclude=done)
        if not found:
            continue
        users = conn.execute(sa.select(app_user.c.id, app_user.c.email).where(app_user.c.org_id == org, app_user.c.active.is_(True))).all()
        meta = {h["ocid"]: h for h in hydrate(conn, found[:MAX_PER_MAIL])}
        for uid, email in users:
            cards = []
            for f in found[:MAX_PER_MAIL]:
                h = meta.get(f["ocid"])
                if h:
                    h = dict(h, reason=f["reason"])
                    cards.append(_card(h, uid, "inventory"))
            html = _mail("Coincidencias con tu inventario", f"{len(found)} concurso(s) vigentes piden productos que ya tienes.",
                         cards, f"{settings.app_url}/alerts")
            send_email(email, f"[GC] {len(found)} coincidencia(s) con tu inventario", html)
            mails += 1
        conn.execute(sa.insert(inventory_alert), [{"org_id": org, "ocid": f["ocid"], "sent_at": now} for f in found])
        n += len(found)
    return {"mails": mails, "tenders": n}


def run_all(conn: sa.Connection, force: bool = False) -> dict:
    return {"saved": run_saved_searches(conn, force), "inventory": run_inventory_alerts(conn)}
