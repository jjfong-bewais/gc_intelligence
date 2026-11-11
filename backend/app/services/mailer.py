"""Envío de correo: console (imprime), file (guarda .html en la bandeja de salida) o resend."""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import httpx

from ..config import settings

log = logging.getLogger("uvicorn.error")  # sale en los logs de Fly


def send_email(to: str, subject: str, html: str) -> bool:
    prov = settings.mail_provider
    if prov == "resend":
        if not settings.resend_api_key:
            log.error("correo: RESEND_API_KEY no está configurada; no se envió «%s» a %s", subject, to)
            return False
        for attempt in range(3):
            try:
                r = httpx.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                    json={"from": settings.mail_from, "to": [to], "subject": subject, "html": html},
                    timeout=20,
                )
                if r.status_code < 300:
                    return True
                # Resend explica el motivo en el cuerpo (dominio sin verificar, clave inválida…); no incluye datos sensibles.
                log.error("correo: Resend respondió %s para «%s» (from=%s): %s", r.status_code, subject,
                          settings.mail_from, r.text[:300])
                if r.status_code < 500 and r.status_code != 429:
                    return False
            except httpx.HTTPError as e:
                log.error("correo: no se pudo contactar a Resend (%s)", type(e).__name__)
            time.sleep(1 + attempt)
        return False
    if prov == "file":
        d = Path(settings.outbox_dir)
        d.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^a-z0-9]+", "-", f"{to}-{subject}".lower())[:80]
        (d / f"{int(time.time() * 1000)}-{safe}.html").write_text(
            f"<!-- to: {to} | subject: {subject} -->\n{html}", encoding="utf-8")
        return True
    print(f"[mail:console] to={to} subject={subject}\n{html[:400]}...")
    return True
