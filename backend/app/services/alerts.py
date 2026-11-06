"""Alertas por correo: búsquedas guardadas e inventario. Idempotente por alert_delivery."""
from __future__ import annotations

from datetime import timedelta
from html import escape

import sqlalchemy as sa

from ..config import settings
from ..db import utcnow
from ..models import alert_delivery, app_user, inventory_alert, saved_search, tender
from ..security import make_link
from .mailer import send_email
from .recommend import inventory_matches
from .search import Filters, hydrate, search_tenders

FREQ = {"immediate": timedelta(minutes=0), "daily": timedelta(hours=23), "weekly": timedelta(days=6, hours=23)}
MAX_PER_MAIL = 25


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
        + f'<div style="margin-top:8px;font-size:13px"><a href="{settings.app_url}/tenders/{h["ocid"]}">Ver en la plataforma</a>'
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


def run_saved_searches(conn: sa.Connection, force: bool = False) -> dict:
    now = utcnow()
    sent = mails = 0
    rows = conn.execute(
        sa.select(saved_search, app_user.c.email).join(app_user, app_user.c.id == saved_search.c.user_id)
        .where(saved_search.c.active.is_(True))).mappings().all()
    for s in rows:
        if not force and not _due(s, now):
            continue
        f = Filters.from_dict(s["filters"])
        f.first_seen_after = s["last_run_at"] or (now - timedelta(days=2))
        if f.status == "all":
            f.status = "open"
        hits, _ = search_tenders(conn, s["q"], s["mode"], f, limit=200)
        done = {r[0] for r in conn.execute(sa.select(alert_delivery.c.ocid).where(alert_delivery.c.saved_search_id == s["id"]))}
        hits = [h for h in hits if h["ocid"] not in done]
        if hits:
            full = hydrate(conn, hits[:MAX_PER_MAIL], s["user_id"])
            html = _mail(f"Alerta: {s['name']}", f"{len(hits)} concurso(s) nuevo(s) coinciden con tu búsqueda.",
                         [_card(h, s["user_id"], "alert") for h in full], _link("unsubscribe", s=s["id"]))
            if send_email(s["email"], f"[GC] {len(hits)} nuevo(s): {s['name']}", html):
                conn.execute(sa.insert(alert_delivery), [{"saved_search_id": s["id"], "ocid": h["ocid"], "sent_at": now} for h in hits])
                sent += len(hits)
                mails += 1
            else:
                continue  # no avanzar last_run_at si el envío falló
        conn.execute(sa.update(saved_search).where(saved_search.c.id == s["id"]).values(last_run_at=now))
    return {"mails": mails, "tenders": sent}


def run_inventory_alerts(conn: sa.Connection) -> dict:
    now = utcnow()
    mails = n = 0
    orgs = conn.execute(sa.select(app_user.c.org_id).distinct()).scalars().all()
    for org in orgs:
        done = {r[0] for r in conn.execute(sa.select(inventory_alert.c.ocid).where(inventory_alert.c.org_id == org))}
        found = inventory_matches(conn, org, settings.match_threshold, since=now - timedelta(days=3), exclude=done)
        if not found:
            continue
        users = conn.execute(sa.select(app_user.c.id, app_user.c.email).where(app_user.c.org_id == org)).all()
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
