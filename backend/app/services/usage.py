"""Captura de uso: qué hace cada usuario dentro de la herramienta.

Un middleware registra cada llamada a la API (usuario, función, estado, latencia) y los handlers pueden
enriquecer el evento con `note(request, ...)`. Los eventos no se escriben en la petición: van a una cola y
un hilo los guarda por lotes (así Neon despertando no suma latencia al usuario). El cliente aporta
`page_view` y el tiempo activo (latido) mediante POST /telemetry.

Sesión = actividad del mismo usuario sin pausas de más de 30 minutos.
"""
from __future__ import annotations

import logging
import queue
import re
import threading
import time
from datetime import datetime, timedelta

import sqlalchemy as sa
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings
from ..db import engine, utcnow
from ..models import usage_event, usage_session
from ..security import COOKIE, read_session

log = logging.getLogger("uvicorn.error")

API_PREFIX = "/api/v1"
SESSION_GAP = timedelta(minutes=30)
MAX_HEARTBEAT = 120  # segundos de tiempo activo que se aceptan por latido

# (prefijo de ruta, función, acciones por método). Se evalúan en orden: lo más específico primero.
_VIEW = {"GET": "view"}
_CRUD = {"GET": "view", "POST": "create", "PUT": "update", "DELETE": "delete"}
RULES: list[tuple[str, str, dict[str, str]]] = [
    ("/tenders/search", "search", {"POST": "search"}),
    ("/tenders/{nog}/similar", "tender_detail", {"GET": "similar"}),
    ("/tenders/{nog}/price-comparables", "tender_detail", {"GET": "price_comparables"}),
    ("/tenders/{nog}", "tender_detail", _VIEW),
    ("/recommendations", "recommendations", _VIEW),
    ("/opportunities", "opportunities", _VIEW),
    ("/dashboard", "dashboard", _VIEW),
    ("/suppliers", "suppliers", _VIEW),
    ("/favorites", "favorites", {"GET": "view", "PUT": "save", "DELETE": "remove"}),
    ("/feedback", "feedback", {"PUT": "vote"}),
    ("/saved-searches", "alerts", _CRUD),
    ("/alerts/run", "alerts", {"POST": "run"}),
    ("/inventory", "inventory", {"GET": "view", "POST": "import", "DELETE": "clear"}),
    ("/org", "settings", _CRUD),
    ("/users", "admin_users", _CRUD),
    ("/auth/login", "auth", {"POST": "login"}),
    ("/auth/logout", "auth", {"POST": "logout"}),
    ("/auth/password", "auth", {"PUT": "password_changed"}),
    ("/auth/email", "auth", {"PUT": "email_changed"}),
    ("/links", "email", {"GET": "link"}),
]
SKIP = ("/health", "/auth/me", "/catalogs", "/telemetry", "/admin", "/data-coverage")

# Pantallas del frontend → función (para los page_view que manda el cliente)
PAGES: list[tuple[str, str]] = [
    ("/search", "search"), ("/tenders", "tender_detail"), ("/recommendations", "recommendations"),
    ("/opportunities", "opportunities"), ("/favorites", "favorites"), ("/inventory", "inventory"),
    ("/alerts", "alerts"), ("/suppliers", "suppliers"), ("/guide", "guide"), ("/settings", "settings"),
    ("/users", "admin_users"), ("/metrics", "admin_metrics"),
]


def classify(method: str, template: str) -> tuple[str, str] | None:
    """(función, acción) de una ruta de la API, o None si no se registra."""
    if template.startswith(SKIP):
        return None
    for prefix, feature, actions in RULES:
        if template == prefix or template.startswith(prefix + "/") or template.startswith(prefix + "{"):
            action = actions.get(method)
            return (feature, action) if action else None
    return None


def page_feature(path: str) -> str:
    if path in ("", "/"):
        return "dashboard"
    for prefix, feature in PAGES:
        if path == prefix or path.startswith(prefix + "/"):
            return feature
    return "other"


def normalize_path(path: str) -> str:
    """Ruta del cliente sin ids ni query: /tenders/123 → /tenders/:id."""
    path = (path or "/").split("?")[0].split("#")[0][:120] or "/"
    path = re.sub(r"^(/tenders)/[^/]+", r"\1/:id", path)
    return re.sub(r"^(/suppliers)/[^/]+", r"\1/:id", path)


def device_of(user_agent: str) -> str:
    return "mobile" if re.search(r"Mobile|Android|iPhone|iPad", user_agent or "") else "desktop"


def local(ts: datetime) -> datetime:
    return ts + timedelta(hours=settings.metrics_tz_offset)


# ------------------------------------------------------------------ captura en la petición
def note(request: Request, **props) -> None:
    """Agrega datos al evento de esta petición. Claves especiales: `user_id` (cuando aún no hay sesión,
    p. ej. en el login) y `action` (para reemplazar la acción por defecto)."""
    d = getattr(request.state, "usage", None)
    if d is not None:
        d.update(props)


def _cookie_user(request: Request) -> int | None:
    token = request.cookies.get(COOKIE)
    return read_session(token) if token else None


def record_request(request: Request, status: int, duration_ms: int) -> None:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if not template:
        return
    if template.startswith(API_PREFIX):  # según la versión de FastAPI la plantilla trae o no el prefijo
        template = template[len(API_PREFIX):]
    cls = classify(request.method, template)
    if not cls:
        return
    feature, action = cls
    props = dict(getattr(request.state, "usage", None) or {})
    uid = props.pop("user_id", None) or _cookie_user(request)
    action = props.pop("action", action)
    if feature == "auth" and action == "login" and status >= 400:
        action = "login_failed"
    if uid is None and action != "login_failed":
        return
    enqueue({
        "kind": "api", "ts": utcnow(), "user_id": uid, "feature": feature, "action": action, "route": template[:120],
        "status": status, "duration_ms": duration_ms, "props": props or None,
        "no_session": feature == "email" or uid is None,
        "device": device_of(request.headers.get("user-agent", "")),
    })


class UsageMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(API_PREFIX):
            return await call_next(request)
        request.state.usage = {}
        t0 = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            try:
                record_request(request, status, int((time.perf_counter() - t0) * 1000))
            except Exception:  # medir nunca debe romper la petición
                log.exception("usage: no se pudo registrar el evento")


# ------------------------------------------------------------------ cola y escritor
_q: queue.Queue = queue.Queue(maxsize=20_000)
_stop = threading.Event()
_thread: threading.Thread | None = None
_lock = threading.Lock()
_SESS: dict[int, dict] = {}  # user_id → {"id", "last"}; solo lo toca el hilo escritor


def enqueue(item: dict) -> None:
    ensure_started()
    try:
        _q.put_nowait(item)
    except queue.Full:  # prefiero perder un evento que frenar la API
        pass


def ensure_started() -> None:
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_run, name="usage-writer", daemon=True)
        _thread.start()


def stop(timeout: float = 5.0) -> None:
    """Vacía la cola y detiene el hilo (al apagar la API)."""
    global _thread
    t = _thread
    if not t:
        return
    _stop.set()
    t.join(timeout)
    _thread = None


def flush(timeout: float = 5.0) -> bool:
    """Espera a que se escriba todo lo encolado (pruebas)."""
    end = time.time() + timeout
    while _q.unfinished_tasks and time.time() < end:
        time.sleep(0.02)
    return not _q.unfinished_tasks


def _run() -> None:
    while True:
        try:
            batch = [_q.get(timeout=0.5)]
        except queue.Empty:
            if _stop.is_set():
                return
            continue
        if not _stop.is_set():
            time.sleep(0.2)  # junta varios eventos en una sola transacción
        while len(batch) < 500:
            try:
                batch.append(_q.get_nowait())
            except queue.Empty:
                break
        try:
            write_batch(batch)
        except Exception:
            _SESS.clear()
            log.exception("usage: no se pudo guardar un lote de %d eventos", len(batch))
        finally:
            for _ in batch:
                _q.task_done()


def _session_for(conn: sa.Connection, uid: int, ts: datetime, it: dict) -> int:
    c = _SESS.get(uid)
    if c and abs(ts - c["last"]) <= SESSION_GAP:
        c["last"] = max(c["last"], ts)
        return c["id"]
    row = conn.execute(
        sa.select(usage_session.c.id, usage_session.c.last_seen_at)
        .where(usage_session.c.user_id == uid, usage_session.c.last_seen_at >= ts - SESSION_GAP)
        .order_by(usage_session.c.last_seen_at.desc()).limit(1)
    ).first()
    if row:
        _SESS[uid] = {"id": row[0], "last": max(row[1], ts)}
        return row[0]
    lt = local(ts)
    sid = conn.execute(sa.insert(usage_session).values(
        user_id=uid, started_at=ts, last_seen_at=ts, day=lt.strftime("%Y-%m-%d"), dow=lt.weekday(), hour=lt.hour,
        active_seconds=0, n_events=0, n_pages=0, entry_source="direct", device=it.get("device", ""),
    )).inserted_primary_key[0]
    _SESS[uid] = {"id": sid, "last": ts}
    return sid


def write_batch(batch: list[dict]) -> None:
    rows: list[dict] = []
    deltas: dict[int, dict] = {}
    with engine.begin() as conn:
        for it in sorted(batch, key=lambda i: i["ts"]):
            ts, uid = it["ts"], it.get("user_id")
            sid = None
            if uid is not None and not it.get("no_session"):
                sid = _session_for(conn, uid, ts, it)
                d = deltas.setdefault(sid, {"last": ts, "ev": 0, "pg": 0, "act": 0})
                d["last"] = max(d["last"], ts)
                if it["kind"] == "heartbeat":
                    d["act"] += max(0, min(int(it.get("seconds", 0)), MAX_HEARTBEAT))
                else:
                    d["ev"] += 1
                    d["pg"] += it["kind"] == "page"
                if it.get("src") == "alert":
                    conn.execute(sa.update(usage_session).where(
                        usage_session.c.id == sid, usage_session.c.entry_source == "direct", usage_session.c.n_events <= 5,
                    ).values(entry_source="alert"))
            if it["kind"] == "heartbeat":
                continue
            lt = local(ts)
            rows.append({
                "ts": ts, "day": lt.strftime("%Y-%m-%d"), "hour": lt.hour, "dow": lt.weekday(), "user_id": uid,
                "session_id": sid, "kind": it["kind"], "feature": it.get("feature", ""), "action": it.get("action", ""),
                "route": it.get("route", ""), "status": it.get("status"), "duration_ms": it.get("duration_ms"),
                "props": it.get("props"),
            })
        if rows:
            conn.execute(sa.insert(usage_event), rows)
        for sid, d in deltas.items():
            conn.execute(sa.update(usage_session).where(usage_session.c.id == sid).values(
                last_seen_at=sa.func.max(usage_session.c.last_seen_at, d["last"]) if engine.dialect.name == "sqlite"
                else sa.func.greatest(usage_session.c.last_seen_at, d["last"]),
                n_events=usage_session.c.n_events + d["ev"], n_pages=usage_session.c.n_pages + d["pg"],
                active_seconds=usage_session.c.active_seconds + d["act"],
            ))


# ------------------------------------------------------------------ retención
def prune(conn: sa.Connection, days: int | None = None) -> dict:
    cutoff = utcnow() - timedelta(days=days or settings.usage_retention_days)
    e = conn.execute(sa.delete(usage_event).where(usage_event.c.ts < cutoff)).rowcount or 0
    s = conn.execute(sa.delete(usage_session).where(usage_session.c.last_seen_at < cutoff)).rowcount or 0
    return {"events": e, "sessions": s}
