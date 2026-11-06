"""Inventario del cliente: importación de CSV y vectores."""
from __future__ import annotations

import csv
import io

import sqlalchemy as sa

from ..models import inventory_item
from .embeddings import embed_inventory
from .text import normalize

MAX_ROWS = 5000
ALIASES = {
    "sku": {"sku", "codigo", "code", "cod", "id"},
    "description": {"descripcion", "description", "producto", "nombre", "articulo", "item"},
    "unit": {"unidad", "unit", "um", "unidad de medida"},
    "unspsc": {"unspsc", "codigo unspsc", "unspsc code"},
}


def _col(header: list[str]) -> dict[str, int]:
    norm = [normalize(h) for h in header]
    out: dict[str, int] = {}
    for key, names in ALIASES.items():
        for i, h in enumerate(norm):
            if h in names and key not in out:
                out[key] = i
    return out


def parse_csv(text: str) -> list[dict]:
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        return []
    cols = _col(rows[0])
    if "description" not in cols:
        raise ValueError("El CSV necesita una columna 'descripcion' (o 'producto').")
    out = []
    for r in rows[1:MAX_ROWS + 1]:
        def get(k: str) -> str:
            i = cols.get(k)
            return (r[i].strip() if i is not None and i < len(r) else "")
        desc = get("description")
        if desc:
            out.append({"sku": get("sku"), "description": desc, "unit": get("unit"), "unspsc": get("unspsc")})
    return out


def import_inventory(conn: sa.Connection, org_id: int, rows: list[dict], replace: bool = True) -> int:
    if replace:
        conn.execute(sa.delete(inventory_item).where(inventory_item.c.org_id == org_id))
    if rows:
        conn.execute(sa.insert(inventory_item), [
            {"org_id": org_id, "sku": r["sku"][:80], "description": r["description"], "unit": r["unit"][:40],
             "unspsc": r["unspsc"][:12], "search_text": normalize(r["description"])} for r in rows
        ])
    embed_inventory(conn)
    return len(rows)
