"""Métricas de uso para administradores: lectura sobre usage_session / usage_event.

Todas las funciones reciben `days` (ventana en días locales, incluido hoy) y `exclude_admins` (por defecto
se excluye a los administradores para que sus pruebas no ensucien los números). Las agrupaciones por día,
hora y día de la semana usan las columnas locales ya guardadas, así que funcionan igual en SQLite y Postgres.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import sqlalchemy as sa

from ..config import settings
from ..db import utcnow
from ..models import app_user, organization, usage_event as ev, usage_session as ss

FEATURE_LABELS = {
    "dashboard": "Resumen", "search": "Buscar", "tender_detail": "Detalle de concurso", "recommendations": "Para ti",
    "opportunities": "Oportunidades", "favorites": "Seguimiento", "inventory": "Inventario", "alerts": "Alertas",
    "suppliers": "Proveedores", "guide": "Guía", "settings": "Ajustes",
}
# Acciones que cuentan para el puntaje de engagement de cada usuario: (función, acción) → peso
SCORE = {
    ("search", "search"): 1, ("tender_detail", "view"): 1, ("recommendations", "view"): 1, ("opportunities", "view"): 1,
    ("suppliers", "view"): 1, ("favorites", "save"): 3, ("feedback", "vote"): 2, ("alerts", "create"): 5,
    ("inventory", "import"): 5,
}
FIRST_VALUE = (("search", "search"), ("favorites", "save"), ("alerts", "create"), ("inventory", "import"))
DAY_FMT = "%Y-%m-%d"
ACTIVE_DAYS, RISK_DAYS = 7, 14  # activo ≤7 días sin entrar; en riesgo ≤14; dormido después
BOUNCE_SECONDS = 10


# ------------------------------------------------------------------ utilidades
def today() -> date:
    return (utcnow() + timedelta(hours=settings.metrics_tz_offset)).date()


def since_day(days: int) -> str:
    return (today() - timedelta(days=days - 1)).strftime(DAY_FMT)


def iso(v):
    return v.isoformat() + "Z" if isinstance(v, datetime) else v


def pct(vals: list[float], p: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 1)


def ratio(a: float, b: float) -> float | None:
    return round(a / b, 4) if b else None


def seconds(s) -> float:
    return max(0.0, (s["last_seen_at"] - s["started_at"]).total_seconds())


def users_in_scope(conn, exclude_admins: bool) -> list[dict]:
    q = (sa.select(app_user.c.id, app_user.c.email, app_user.c.name, app_user.c.role, app_user.c.active,
                   app_user.c.must_change_password, app_user.c.created_at, organization.c.name.label("company"))
         .select_from(app_user.outerjoin(organization, organization.c.id == app_user.c.org_id)))
    if exclude_admins:
        q = q.where(app_user.c.role != "admin")
    return [dict(r) for r in conn.execute(q.order_by(app_user.c.id)).mappings()]


def _sessions(conn, ids: list[int], since: str) -> list[dict]:
    if not ids:
        return []
    return [dict(r) for r in conn.execute(sa.select(ss).where(ss.c.day >= since, ss.c.user_id.in_(ids))).mappings()]


def _days(n: int) -> list[str]:
    t = today()
    return [(t - timedelta(days=i)).strftime(DAY_FMT) for i in range(n - 1, -1, -1)]


# ------------------------------------------------------------------ resumen
def overview(conn, days: int, exclude_admins: bool) -> dict:
    users = users_in_scope(conn, exclude_admins)
    ids = [u["id"] for u in users]
    load = max(days, 30)
    allsess = _sessions(conn, ids, since_day(load))
    since = since_day(days)
    sess = [s for s in allsess if s["day"] >= since]
    ever = set(conn.execute(sa.select(ss.c.user_id).where(ss.c.user_id.in_(ids)).distinct()).scalars()) if ids else set()

    by_day: dict[str, set] = defaultdict(set)
    for s in allsess:
        by_day[s["day"]].add(s["user_id"])
    t = today()
    dau = len(by_day.get(t.strftime(DAY_FMT), ()))
    wau = len({u for d in _days(7) for u in by_day.get(d, ())})
    mau = len({u for d in _days(30) for u in by_day.get(d, ())})
    avg_dau = sum(len(by_day.get(d, ())) for d in _days(30)) / 30

    events_by_day = {}
    if ids:
        events_by_day = dict(conn.execute(
            sa.select(ev.c.day, sa.func.count()).where(ev.c.day >= since, ev.c.user_id.in_(ids), ev.c.session_id.isnot(None))
            .group_by(ev.c.day)).all())
    sess_by_day = Counter(s["day"] for s in sess)
    active_by_day: Counter = Counter()
    for s in sess:
        active_by_day[s["day"]] += s["active_seconds"]
    series = [{"day": d, "dau": len({*by_day.get(d, ())}), "sessions": sess_by_day.get(d, 0),
               "active_minutes": round(active_by_day.get(d, 0) / 60, 1), "events": events_by_day.get(d, 0)} for d in _days(days)]

    durations = [seconds(s) for s in sess]
    active = [s["active_seconds"] for s in sess if s["active_seconds"] > 0]
    bounces = sum(1 for s in sess if s["n_pages"] <= 1 and seconds(s) < BOUNCE_SECONDS)
    heat = [[0] * 24 for _ in range(7)]
    for s in sess:
        heat[s["dow"]][s["hour"]] += 1
    active_users = len({s["user_id"] for s in sess})
    return {
        "window_days": days, "from": since, "to": t.strftime(DAY_FMT), "exclude_admins": exclude_admins,
        "kpis": {
            "users_total": len(users), "activated": sum(1 for u in users if not u["must_change_password"]),
            "never_entered": sum(1 for u in users if u["id"] not in ever), "active_users": active_users,
            "dau": dau, "wau": wau, "mau": mau, "stickiness": ratio(avg_dau, mau),
            "sessions": len(sess), "sessions_per_active_user": round(len(sess) / active_users, 1) if active_users else None,
            "duration_median_s": pct(durations, 0.5), "duration_p90_s": pct(durations, 0.9),
            "active_median_s": pct(active, 0.5), "pages_per_session": round(sum(s["n_pages"] for s in sess) / len(sess), 1) if sess else None,
            "bounce_rate": ratio(bounces, len(sess)), "events": sum(events_by_day.values()),
        },
        "series": series, "heatmap": heat,
        "entry_sources": dict(Counter(s["entry_source"] for s in sess)),
        "devices": dict(Counter(s["device"] or "desconocido" for s in sess)),
    }


# ------------------------------------------------------------------ usuarios
def _status(last_active: datetime | None) -> str:
    if last_active is None:
        return "never"
    age = (utcnow() - last_active).days
    return "active" if age <= ACTIVE_DAYS else "at_risk" if age <= RISK_DAYS else "dormant"


def users(conn, days: int, exclude_admins: bool) -> dict:
    us = users_in_scope(conn, exclude_admins)
    ids = [u["id"] for u in us]
    since = since_day(days)
    life = {r["user_id"]: r for r in conn.execute(
        sa.select(ss.c.user_id, sa.func.min(ss.c.started_at).label("first"), sa.func.max(ss.c.last_seen_at).label("last"))
        .where(ss.c.user_id.in_(ids)).group_by(ss.c.user_id)).mappings()} if ids else {}
    sess = defaultdict(list)
    for s in _sessions(conn, ids, since):
        sess[s["user_id"]].append(s)
    counts: dict[int, Counter] = defaultdict(Counter)
    if ids:
        for uid, feat, act, n in conn.execute(
                sa.select(ev.c.user_id, ev.c.feature, ev.c.action, sa.func.count()).where(ev.c.day >= since, ev.c.user_id.in_(ids), ev.c.kind == "api")
                .group_by(ev.c.user_id, ev.c.feature, ev.c.action)):
            counts[uid][(feat, act)] = n
    first_value: dict[int, datetime] = {}
    if ids:
        for uid, feat, act, ts in conn.execute(
                sa.select(ev.c.user_id, ev.c.feature, ev.c.action, sa.func.min(ev.c.ts)).where(ev.c.user_id.in_(ids), ev.c.kind == "api")
                .group_by(ev.c.user_id, ev.c.feature, ev.c.action)):
            if (feat, act) in FIRST_VALUE and (uid not in first_value or ts < first_value[uid]):
                first_value[uid] = ts
    out = []
    for u in us:
        c, ses, lf = counts[u["id"]], sess[u["id"]], life.get(u["id"])
        first, last = (lf["first"], lf["last"]) if lf else (None, None)
        out.append({
            "id": u["id"], "email": u["email"], "name": u["name"], "company": u["company"], "role": u["role"], "active": u["active"],
            "created_at": iso(u["created_at"]), "first_login_at": iso(first), "last_active_at": iso(last), "status": _status(last),
            "days_to_first_login": round((first - u["created_at"]).total_seconds() / 86400, 1) if first and u["created_at"] else None,
            "days_to_first_value": round((first_value[u["id"]] - u["created_at"]).total_seconds() / 86400, 1)
            if u["id"] in first_value and u["created_at"] else None,
            "sessions": len(ses), "active_minutes": round(sum(s["active_seconds"] for s in ses) / 60, 1),
            "duration_median_s": pct([seconds(s) for s in ses], 0.5),
            "searches": c[("search", "search")], "tender_views": c[("tender_detail", "view")],
            "favorites_added": c[("favorites", "save")], "feedback": c[("feedback", "vote")],
            "saved_searches": c[("alerts", "create")], "inventory_imports": c[("inventory", "import")],
            "score": sum(w * c[k] for k, w in SCORE.items()),
        })
    out.sort(key=lambda r: (-r["score"], -r["sessions"], r["email"]))
    return {"window_days": days, "exclude_admins": exclude_admins, "items": out,
            "status_counts": dict(Counter(r["status"] for r in out))}


def user_detail(conn, uid: int, days: int) -> dict | None:
    u = conn.execute(
        sa.select(app_user.c.id, app_user.c.email, app_user.c.name, app_user.c.role, app_user.c.created_at, organization.c.name.label("company"))
        .select_from(app_user.outerjoin(organization, organization.c.id == app_user.c.org_id)).where(app_user.c.id == uid)).mappings().first()
    if not u:
        return None
    since = since_day(days)
    ses = [dict(r) for r in conn.execute(sa.select(ss).where(ss.c.user_id == uid, ss.c.day >= since).order_by(ss.c.started_at.desc())).mappings()]
    per_feature = [{"feature": f, "label": FEATURE_LABELS.get(f, f), "action": a, "count": n} for f, a, n in conn.execute(
        sa.select(ev.c.feature, ev.c.action, sa.func.count()).where(ev.c.user_id == uid, ev.c.day >= since, ev.c.kind == "api")
        .group_by(ev.c.feature, ev.c.action).order_by(sa.desc(sa.func.count())))]
    daily = dict(conn.execute(sa.select(ev.c.day, sa.func.count()).where(ev.c.user_id == uid, ev.c.day >= since).group_by(ev.c.day)).all())
    events = [{"ts": iso(r["ts"]), "kind": r["kind"], "feature": r["feature"], "label": FEATURE_LABELS.get(r["feature"], r["feature"]),
               "action": r["action"], "status": r["status"], "props": r["props"]}
              for r in conn.execute(sa.select(ev).where(ev.c.user_id == uid, ev.c.day >= since).order_by(ev.c.ts.desc()).limit(80)).mappings()]
    return {
        "user": {"id": u["id"], "email": u["email"], "name": u["name"], "company": u["company"], "role": u["role"], "created_at": iso(u["created_at"])},
        "window_days": days,
        "sessions": [{"started_at": iso(s["started_at"]), "duration_s": seconds(s), "active_s": s["active_seconds"], "events": s["n_events"],
                      "pages": s["n_pages"], "source": s["entry_source"], "device": s["device"]} for s in ses[:25]],
        "features": per_feature, "series": [{"day": d, "events": daily.get(d, 0)} for d in _days(days)], "events": events,
    }


# ------------------------------------------------------------------ funcionalidades
def features(conn, days: int, exclude_admins: bool) -> dict:
    us = users_in_scope(conn, exclude_admins)
    ids = [u["id"] for u in us]
    since = since_day(days)
    stat: dict[str, dict] = defaultdict(lambda: {"visits": 0, "actions": 0, "users": set(), "visit_users": set(), "last": None})
    sessions_total = 0
    if ids:
        sessions_total = conn.execute(sa.select(sa.func.count()).select_from(ss).where(ss.c.day >= since, ss.c.user_id.in_(ids))).scalar() or 0
        for feat, kind, act, uid, n, last in conn.execute(
                sa.select(ev.c.feature, ev.c.kind, ev.c.action, ev.c.user_id, sa.func.count(), sa.func.max(ev.c.ts))
                .where(ev.c.day >= since, ev.c.user_id.in_(ids), ev.c.session_id.isnot(None), ev.c.feature != "", ev.c.feature != "auth")
                .group_by(ev.c.feature, ev.c.kind, ev.c.action, ev.c.user_id)):
            s = stat[feat]
            s["users"].add(uid)
            if kind == "page":
                s["visits"] += n
                s["visit_users"].add(uid)
            elif act not in ("view",):
                s["actions"] += n
            if s["last"] is None or last > s["last"]:
                s["last"] = last
    # minutos por función: tiempo hasta la siguiente pantalla de la misma sesión (máx. 5 min por visita)
    dwell: Counter = Counter()
    if ids:
        prev = None
        for sid, feat, ts in conn.execute(sa.select(ev.c.session_id, ev.c.feature, ev.c.ts).where(
                ev.c.day >= since, ev.c.user_id.in_(ids), ev.c.kind == "page", ev.c.session_id.isnot(None)).order_by(ev.c.session_id, ev.c.ts).limit(200_000)):
            if prev and prev[0] == sid:
                dwell[prev[1]] += min((ts - prev[2]).total_seconds(), 300)
            prev = (sid, feat, ts)
    rows = []
    for f in list(FEATURE_LABELS) + sorted(set(stat) - set(FEATURE_LABELS)):
        s = stat.get(f)
        n_users = len(s["users"]) if s else 0
        rows.append({
            "feature": f, "label": FEATURE_LABELS.get(f, f), "visits": s["visits"] if s else 0, "actions": s["actions"] if s else 0,
            "users": n_users, "adoption": ratio(n_users, len(ids)), "visits_per_user": round(s["visits"] / max(1, len(s["visit_users"])), 1) if s else 0,
            "minutes": round(dwell.get(f, 0) / 60, 1), "last_used_at": iso(s["last"]) if s else None,
        })
    rows.sort(key=lambda r: (-(r["visits"] + r["actions"]), r["label"]))
    return {"window_days": days, "exclude_admins": exclude_admins, "users_in_scope": len(ids), "items": rows,
            "unused": [r["label"] for r in rows if not r["visits"] and not r["actions"] and r["feature"] in FEATURE_LABELS],
            "funnel": _funnel(conn, ids, since, sessions_total)}


def _funnel(conn, ids: list[int], since: str, sessions_total: int) -> list[dict]:
    """Sesiones que hicieron una búsqueda, de ellas las que abrieron un concurso, y de ellas las que lo siguieron."""
    marks: dict[int, set] = defaultdict(set)
    if ids:
        for sid, feat, act in conn.execute(sa.select(ev.c.session_id, ev.c.feature, ev.c.action).where(
                ev.c.day >= since, ev.c.user_id.in_(ids), ev.c.kind == "api", ev.c.session_id.isnot(None)).distinct()):
            marks[sid].add((feat, act))
    s1 = {s for s, m in marks.items() if ("search", "search") in m}
    s2 = {s for s in s1 if ("tender_detail", "view") in marks[s]}
    s3 = {s for s in s2 if ("favorites", "save") in marks[s]}
    return [{"step": "Sesiones", "count": sessions_total}, {"step": "Buscaron", "count": len(s1)},
            {"step": "Abrieron un concurso", "count": len(s2)}, {"step": "Lo siguieron (favorito)", "count": len(s3)}]


# ------------------------------------------------------------------ búsquedas
def searches(conn, days: int, exclude_admins: bool) -> dict:
    us = users_in_scope(conn, exclude_admins)
    ids = [u["id"] for u in us]
    who = {u["id"]: u["company"] or u["email"] for u in us}
    since = since_day(days)
    rows = []
    detail_sessions: set = set()
    if ids:
        rows = [dict(r) for r in conn.execute(sa.select(ev.c.ts, ev.c.day, ev.c.user_id, ev.c.session_id, ev.c.props, ev.c.duration_ms).where(
            ev.c.day >= since, ev.c.user_id.in_(ids), ev.c.feature == "search", ev.c.action == "search").order_by(ev.c.ts).limit(20_000)).mappings()]
        detail_sessions = set(conn.execute(sa.select(ev.c.session_id).where(
            ev.c.day >= since, ev.c.user_id.in_(ids), ev.c.feature == "tender_detail", ev.c.action == "view", ev.c.session_id.isnot(None)).distinct()).scalars())
    first = [r for r in rows if not (r["props"] or {}).get("offset")]  # sin contar «ver más»
    terms: dict[str, dict] = {}
    modes, filters = Counter(), Counter()
    zero = known = with_detail = 0
    per_day, per_user = Counter(), Counter()
    embed = 0
    for r in first:
        p = r["props"] or {}
        q = (p.get("q") or "").strip()
        per_day[r["day"]] += 1
        per_user[r["user_id"]] += 1
        modes[p.get("mode", "hybrid")] += 1
        embed += bool(p.get("used_embedding"))
        for k in (p.get("filters") or {}):
            filters[k] += 1
        total = p.get("total")
        if total is not None:
            known += 1
            zero += total == 0
        if r["session_id"] in detail_sessions:
            with_detail += 1
        if q:
            t = terms.setdefault(q.lower(), {"term": q, "count": 0, "users": set(), "zero": 0})
            t["count"] += 1
            t["users"].add(r["user_id"])
            t["zero"] += total == 0
    top = sorted(terms.values(), key=lambda t: (-t["count"], t["term"]))[:25]
    lat = [r["duration_ms"] for r in first if r["duration_ms"] is not None]
    return {
        "window_days": days, "exclude_admins": exclude_admins,
        "kpis": {"searches": len(first), "searchers": len(per_user), "per_active_searcher": round(len(first) / len(per_user), 1) if per_user else None,
                 "zero_result_rate": ratio(zero, known), "search_to_detail_rate": ratio(with_detail, len(first)),
                 "latency_p50_ms": pct(lat, 0.5), "latency_p95_ms": pct(lat, 0.95), "embedding_searches": embed},
        "series": [{"day": d, "searches": per_day.get(d, 0)} for d in _days(days)],
        "modes": dict(modes), "filters": [{"filter": k, "count": n} for k, n in filters.most_common(15)],
        "top_terms": [{"term": t["term"], "count": t["count"], "users": len(t["users"]), "zero_results": t["zero"]} for t in top],
        "zero_terms": [{"term": t["term"], "count": t["zero"]} for t in sorted(terms.values(), key=lambda t: -t["zero"]) if t["zero"]][:15],
        "top_users": [{"user_id": uid, "who": who.get(uid, str(uid)), "count": n} for uid, n in per_user.most_common(10)],
        "recent": [{"ts": iso(r["ts"]), "who": who.get(r["user_id"], str(r["user_id"])), "q": (r["props"] or {}).get("q", ""),
                    "mode": (r["props"] or {}).get("mode"), "total": (r["props"] or {}).get("total"),
                    "filters": list(((r["props"] or {}).get("filters") or {}).keys())} for r in reversed(first[-30:])],
    }


# ------------------------------------------------------------------ retención
def retention(conn, exclude_admins: bool, weeks: int = 13) -> dict:
    """Cohortes por semana de la primera sesión; % de cada cohorte con sesión en la semana +N."""
    us = users_in_scope(conn, exclude_admins)
    ids = [u["id"] for u in us]
    since = since_day(weeks * 7)
    by_user: dict[int, set] = defaultdict(set)
    for s in _sessions(conn, ids, since):
        d = datetime.strptime(s["day"], DAY_FMT).date()
        by_user[s["user_id"]].add(d - timedelta(days=d.weekday()))
    t = today()
    this_week = t - timedelta(days=t.weekday())
    cohorts: dict[date, list] = defaultdict(list)
    for uid, wk in by_user.items():
        cohorts[min(wk)].append(uid)
    out = []
    for w in sorted(cohorts):
        elapsed = (this_week - w).days // 7
        members = cohorts[w]
        out.append({"week": w.strftime(DAY_FMT), "size": len(members),
                    "retention": [round(sum(1 for u in members if (w + timedelta(weeks=k)) in by_user[u]) / len(members), 3) if k <= elapsed else None
                                  for k in range(weeks)]})
    return {"weeks": weeks, "exclude_admins": exclude_admins, "cohorts": out}


# ------------------------------------------------------------------ salud técnica
def health(conn, days: int, exclude_admins: bool) -> dict:
    us = users_in_scope(conn, exclude_admins)
    ids = [u["id"] for u in us]
    since = since_day(days)
    per: dict[str, dict] = defaultdict(lambda: {"n": 0, "e4": 0, "e5": 0, "ms": []})
    recent_errors = []
    if ids:
        for r in conn.execute(sa.select(ev.c.ts, ev.c.route, ev.c.status, ev.c.duration_ms, ev.c.user_id).where(
                ev.c.day >= since, ev.c.user_id.in_(ids), ev.c.kind == "api").order_by(ev.c.ts).limit(100_000)).mappings():
            p = per[r["route"]]
            p["n"] += 1
            st = r["status"] or 0
            p["e5"] += st >= 500
            p["e4"] += 400 <= st < 500
            if r["duration_ms"] is not None:
                p["ms"].append(r["duration_ms"])
            if st >= 500:
                recent_errors.append({"ts": iso(r["ts"]), "route": r["route"], "status": st})
    failed_logins = conn.execute(sa.select(sa.func.count()).select_from(ev).where(ev.c.day >= since, ev.c.action == "login_failed")).scalar() or 0
    items = [{"route": route, "count": p["n"], "errors_4xx": p["e4"], "errors_5xx": p["e5"], "error_rate": ratio(p["e5"], p["n"]),
              "p50_ms": pct(p["ms"], 0.5), "p95_ms": pct(p["ms"], 0.95)} for route, p in per.items()]
    items.sort(key=lambda r: -(r["p95_ms"] or 0))
    total = sum(p["n"] for p in per.values())
    return {"window_days": days, "exclude_admins": exclude_admins,
            "kpis": {"requests": total, "errors_5xx": sum(p["e5"] for p in per.values()), "errors_4xx": sum(p["e4"] for p in per.values()),
                     "failed_logins": failed_logins},
            "items": items[:40], "recent_errors": list(reversed(recent_errors[-20:]))}
