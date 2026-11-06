"""Envío de correo: console (imprime), file (guarda .html en la bandeja de salida) o resend."""
from __future__ import annotations

import re
import time
from pathlib import Path

import httpx

from ..config import settings


def send_email(to: str, subject: str, html: str) -> bool:
    prov = settings.mail_provider
    if prov == "resend":
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
                if r.status_code < 500 and r.status_code != 429:
                    return False
            except httpx.HTTPError:
                pass
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
