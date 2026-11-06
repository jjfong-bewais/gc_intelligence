"""Normalización de texto en español (mayúsculas, tildes, abreviaturas)."""
from __future__ import annotations

import hashlib
import re
import unicodedata

STOPWORDS = {
    "de", "la", "el", "los", "las", "y", "en", "para", "con", "por", "del", "al",
    "un", "una", "a", "o", "e", "que", "se", "su", "sus", "lo",
}

# Abreviaturas frecuentes en Guatecompras (ampliable).
ABBREV = {
    "retroexc": "retroexcavadora",
    "mant": "mantenimiento",
    "adq": "adquisicion",
    "serv": "servicio",
    "equip": "equipo",
    "mat": "material",
}


def normalize(text: str | None) -> str:
    """minúsculas, sin tildes, solo letras y números separados por espacios."""
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    if not s:
        return ""
    return " ".join(ABBREV.get(w, w) for w in s.split())


def tokens(text: str | None) -> list[str]:
    out: list[str] = []
    for w in normalize(text).split():
        if w in STOPWORDS or len(w) < 2:
            continue
        if w not in out:
            out.append(w)
    return out


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def unspsc_class(code: str | None) -> str:
    """Clase UNSPSC = primeros 6 dígitos (segmento 2, familia 4, clase 6, commodity 8)."""
    return (code or "")[:6]
