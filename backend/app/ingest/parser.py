"""Convierte un `compiledRelease` OCDS de Guatecompras en filas normalizadas.

Forma observada en los archivos mensuales (records[].compiledRelease): parties,
buyer, bids.details, tender (items, tenderers, documents, tenderPeriod), awards,
contracts. Todo se lee de forma tolerante: cualquier campo puede faltar.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from ..services.text import normalize, sha1, unspsc_class


def parse_dt(value: Any) -> datetime | None:
    """ISO 8601 -> UTC sin zona. Tolera los errores de fecha que reporta el registro OCP."""
    if not value or not isinstance(value, str):
        return None
    s = re.sub(r"^(\d{4})\s+", r"\1", value.strip())  # espacio extra tras el año
    s = s.replace("Z", "+00:00")
    if "T" not in s:
        s = s.replace(" ", "T", 1)
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)  # más de 6 decimales
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt if 2000 <= dt.year <= 2100 else None


def _nog(*candidates: Any) -> int | None:
    for c in candidates:
        m = re.search(r"(\d{5,})\s*$", str(c or ""))
        if m:
            return int(m.group(1))
    return None


def _amount(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("amount")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _currency(value: Any) -> str | None:
    return value.get("currency") if isinstance(value, dict) else None


def parse_release(rel: dict) -> dict | None:
    ocid = rel.get("ocid")
    tdr = rel.get("tender") or {}
    nog = _nog(tdr.get("id"), ocid)
    if not ocid or nog is None:
        return None

    # ------------------------------------------------------------ partes
    parties: dict[str, dict] = {}
    unit_name = ""
    for p in rel.get("parties") or []:
        pid = p.get("id")
        if not pid:
            continue
        roles = p.get("roles") or []
        det = p.get("details") or {}
        if "buyer" in roles:
            kind = "unit" if str(pid).startswith("GT-GCUC") else "entity"
            if kind == "unit" and not unit_name:
                unit_name = p.get("name") or ""
        else:
            kind = "supplier"
        member = (p.get("memberOf") or [{}])[0] or {}
        parties[pid] = {
            "id": pid, "kind": kind, "name": p.get("name") or pid,
            "name_norm": normalize(p.get("name") or ""),
            "entity_type": ((det.get("entityType") or {}).get("description")),
            "level": ((det.get("level") or {}).get("description")),
            "region": (p.get("address") or {}).get("region"),
            "parent_id": member.get("id"),
        }

    buyer = rel.get("buyer") or {}
    pe = tdr.get("procuringEntity") or {}
    buyer_id = pe.get("id") or buyer.get("id")
    buyer_name = pe.get("name") or buyer.get("name") or ""

    # ------------------------------------------------------------ ítems
    items: list[dict] = []
    for idx, it in enumerate(tdr.get("items") or []):
        desc = (it.get("description") or "").strip()
        attrs = " ".join(
            str(a.get("value") or "") for a in (it.get("attributes") or [])
            if "caracter" in normalize(a.get("name"))
        )
        embed_text = f"{desc}. {attrs}".strip(". ")[:600] if attrs and attrs != desc else desc
        cls = (it.get("classification") or {}).get("id") or ""
        items.append({
            "id": f"{ocid}:{it.get('id') or idx}", "ocid": ocid, "idx": idx,
            "description": desc, "unspsc": str(cls),
            "quantity": _amount(it.get("quantity")),
            "unit": (it.get("unit") or {}).get("name"),
            "search_text": "",  # no se usa en búsquedas; ahorra espacio
            "embed_text": embed_text, "text_hash": sha1(embed_text),
        })
    classes = Counter(unspsc_class(i["unspsc"]) for i in items if i["unspsc"])
    unspsc_main = classes.most_common(1)[0][0] if classes else None

    title = (tdr.get("title") or "").strip()
    tender_embed = (title + ". " + "; ".join(i["description"] for i in items[:8]))[:1200].strip(". ")
    period = tdr.get("tenderPeriod") or {}
    row = {
        "ocid": ocid, "nog": nog, "title": title,
        "status": tdr.get("status"), "status_details": tdr.get("statusDetails"),
        "method": tdr.get("procurementMethod"),
        "method_details": tdr.get("procurementMethodDetails"),
        "category": tdr.get("mainProcurementCategory"),
        "published_at": parse_dt(tdr.get("datePublished") or period.get("startDate")),
        "deadline_at": parse_dt(period.get("endDate")),
        "buyer_id": buyer_id, "buyer_name": buyer_name, "buyer_norm": normalize(buyer_name),
        "unit_name": unit_name, "n_tenderers": tdr.get("numberOfTenderers"),
        "n_items": len(items), "unspsc_main": unspsc_main,
        "release_date": rel.get("date"),
        "search_text": normalize(f"{nog} {title} " + " ".join(i["description"] for i in items))[:2000],
        "embed_text": tender_embed, "text_hash": sha1(tender_embed),
    }

    # ------------------------------------------------------------ ofertas
    bids: list[dict] = []
    for b in ((rel.get("bids") or {}).get("details")) or []:
        t0 = (b.get("tenderers") or [{}])[0] or {}
        bids.append({
            "id": f"{ocid}:{b.get('id') or len(bids)}", "ocid": ocid,
            "supplier_id": t0.get("id"), "supplier_name": t0.get("name") or "",
            "amount": _amount(b.get("value")), "currency": _currency(b.get("value")),
            "status": b.get("status"), "date": parse_dt(b.get("date")),
        })
        if t0.get("id") and t0["id"] not in parties:
            parties[t0["id"]] = _supplier(t0)
    for t0 in tdr.get("tenderers") or []:
        if t0.get("id") and t0["id"] not in parties:
            parties[t0["id"]] = _supplier(t0)

    # ------------------------------------------------------------ adjudicaciones
    awards: list[dict] = []
    for a in rel.get("awards") or []:
        for s in a.get("suppliers") or []:
            if not s.get("id"):
                continue
            awards.append({
                "id": f"{ocid}:{a.get('id') or 'a'}:{s['id']}", "ocid": ocid,
                "award_ref": str(a.get("id") or ""), "supplier_id": s["id"],
                "supplier_name": s.get("name") or "",
                "amount": _amount(a.get("value")), "currency": _currency(a.get("value")),
                "status": a.get("status"), "status_details": a.get("statusDetails"),
                "date": parse_dt(a.get("date")),
            })
            if s["id"] not in parties:
                parties[s["id"]] = _supplier(s)

    contracts: list[dict] = []
    docs: list[dict] = []
    for d in tdr.get("documents") or []:
        docs.append(_doc(ocid, d, len(docs)))
    for c in rel.get("contracts") or []:
        contracts.append({
            "id": f"{ocid}:{c.get('id') or len(contracts)}", "ocid": ocid,
            "award_ref": str(c.get("awardID") or ""), "number": c.get("contractNumber"),
            "signed_at": parse_dt(c.get("dateSigned")),
            "amount": _amount(c.get("value")), "currency": _currency(c.get("value")),
        })
        for d in c.get("documents") or []:
            docs.append(_doc(ocid, d, len(docs)))

    # ------------------------------------------------------------ precio unitario derivado
    # Solo cuando hay un único renglón y una única adjudicación: de lo contrario
    # el monto total no permite repartir el precio por ítem.
    prices: list[dict] = []
    if len(items) == 1 and len(awards) == 1:
        it, aw = items[0], awards[0]
        if it["quantity"] and it["quantity"] > 0 and aw["amount"] and aw["amount"] > 0:
            prices.append({
                "ocid": ocid, "item_id": it["id"], "unspsc": it["unspsc"],
                "quantity": it["quantity"], "unit": it["unit"],
                "unit_price": aw["amount"] / it["quantity"], "amount": aw["amount"],
                "currency": aw["currency"], "supplier_id": aw["supplier_id"],
                "supplier_name": aw["supplier_name"],
                "awarded_at": aw["date"] or row["published_at"],
            })

    # Ahorro de espacio: solo se vectorizan los renglones que se consultan por ítem
    # (concursos vigentes -> cruce con inventario; renglones con precio -> comparables).
    if tdr.get("statusDetails") != "Vigente":
        priced = {p["item_id"] for p in prices}
        for it in items:
            if it["id"] not in priced:
                it["embed_text"], it["text_hash"] = "", sha1("")

    return {
        "tender": row, "items": items, "parties": list(parties.values()), "bids": bids,
        "awards": awards, "contracts": contracts, "docs": docs, "prices": prices,
    }


def _supplier(p: dict) -> dict:
    name = p.get("name") or p.get("id")
    return {
        "id": p["id"], "kind": "supplier", "name": name, "name_norm": normalize(name),
        "entity_type": None, "level": None, "region": None, "parent_id": None,
    }


def _doc(ocid: str, d: dict, n: int) -> dict:
    return {
        "id": f"{ocid}:{d.get('id') or n}", "ocid": ocid, "doc_type": d.get("documentType"),
        "title": d.get("title"), "url": d.get("url"), "published_at": parse_dt(d.get("datePublished")),
    }
