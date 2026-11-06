"""Datos SINTÉTICOS con la misma forma que los registros reales de Guatecompras.

Todo lo generado es ficticio (entidades, empresas, NIT, montos). Sirve para la demo
local y las pruebas sin depender de la red ni del API real.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

DEMO_NIT = "GT-NIT-9000001"
DEMO_ORG_NAME = "Distribuidora Demo, S.A."

# familia -> (códigos UNSPSC, variantes (descripción, unidad), precio base GTQ, rango de cantidad, categoría)
FAMILIES = {
    "papel": ("14111507", [("PAPEL BOND TAMAÑO CARTA 75 GRAMOS", "Resma"), ("PAPEL BOND TAMAÑO OFICIO 75 GRAMOS", "Resma"), ("PAPEL BOND CARTA 20 LIBRAS", "Resma")], 31, (200, 5000), "goods"),
    "toner": ("44103103", [("TÓNER HP 78A NEGRO", "Unidad"), ("TÓNER BROTHER TN-660 NEGRO", "Unidad"), ("CARTUCHO DE TINTA EPSON 664 NEGRO", "Unidad"), ("TÓNER SAMSUNG MLT-D111S", "Unidad")], 560, (10, 300), "goods"),
    "limpieza": ("47131800", [("DESINFECTANTE LÍQUIDO GALÓN", "Galón"), ("CLORO LÍQUIDO PARA LIMPIEZA GALÓN", "Galón"), ("JABÓN LÍQUIDO PARA MANOS GALÓN", "Galón"), ("ESCOBA PLÁSTICA", "Unidad"), ("TRAPEADOR DE ALGODÓN", "Unidad")], 34, (50, 2000), "goods"),
    "computo": ("43211503", [("COMPUTADORA PORTÁTIL 15 PULGADAS CORE I5 8GB RAM", "Unidad"), ("COMPUTADORA DE ESCRITORIO CORE I5 16GB RAM", "Unidad"), ("MONITOR LED 24 PULGADAS", "Unidad"), ("IMPRESORA MULTIFUNCIONAL LÁSER", "Unidad")], 4800, (2, 80), "goods"),
    "llantas": ("25172504", [("LLANTA 265/70 R16 PARA PICK UP", "Unidad"), ("LLANTA 205/55 R16 PARA SEDAN", "Unidad"), ("LLANTA 11R22.5 PARA CAMIÓN", "Unidad")], 1700, (4, 120), "goods"),
    "combustible": ("15101505", [("DIÉSEL ALTO AZUFRE", "Galón"), ("GASOLINA SÚPER", "Galón"), ("GASOLINA REGULAR", "Galón")], 30, (2000, 50000), "goods"),
    "cemento": ("30111505", [("CEMENTO GRIS 4000 PSI SACO 42.5 KG", "Saco"), ("CEMENTO PORTLAND SACO 42.5 KG", "Saco")], 86, (100, 5000), "goods"),
    "hierro": ("30102200", [("VARILLA DE HIERRO LEGÍTIMO 3/8 PULGADA", "Unidad"), ("VARILLA CORRUGADA 1/2 PULGADA", "Unidad")], 58, (100, 3000), "goods"),
    "tuberia": ("40142007", [("TUBERÍA PVC 2 PULGADAS 160 PSI", "Unidad"), ("TUBERÍA PVC 4 PULGADAS PARA DRENAJE", "Unidad"), ("CODO PVC 2 PULGADAS", "Unidad")], 95, (50, 1500), "goods"),
    "medicinas": ("51121703", [("ACETAMINOFÉN 500 MG TABLETA", "Tableta"), ("IBUPROFENO 400 MG TABLETA", "Tableta"), ("AMOXICILINA 500 MG CÁPSULA", "Cápsula"), ("SUERO FISIOLÓGICO 0.9% 1000 ML", "Unidad")], 4.5, (10000, 200000), "goods"),
    "insumos_med": ("42132203", [("GUANTES DE LÁTEX PARA EXAMEN CAJA DE 100", "Caja"), ("MASCARILLA QUIRÚRGICA CAJA DE 50", "Caja"), ("JERINGA DESECHABLE 5 ML", "Unidad")], 62, (100, 6000), "goods"),
    "uniformes": ("53102700", [("UNIFORME OPERATIVO PANTALÓN Y CAMISA", "Juego"), ("BOTAS DE SEGURIDAD", "Par"), ("CHALECO REFLECTIVO", "Unidad")], 210, (50, 1500), "goods"),
    "alimentos": ("50202301", [("AGUA PURA EN GARRAFÓN 5 GALONES", "Garrafón"), ("FRIJOL NEGRO LIBRA", "Libra"), ("ARROZ BLANCO LIBRA", "Libra"), ("GALLETAS PARA REFACCIÓN ESCOLAR", "Paquete")], 7.5, (500, 40000), "goods"),
    "mobiliario": ("56101500", [("ESCRITORIO METÁLICO EJECUTIVO", "Unidad"), ("SILLA SECRETARIAL GIRATORIA", "Unidad"), ("ARCHIVO METÁLICO 4 GAVETAS", "Unidad")], 1100, (5, 120), "goods"),
    "pintura": ("31211501", [("PINTURA LÁTEX BLANCA CUBETA 5 GALONES", "Cubeta"), ("PINTURA ESMALTE GALÓN", "Galón")], 340, (10, 400), "goods"),
    "maquinaria": ("72141701", [("ARRENDAMIENTO DE RETROEXCAVADORA POR HORA", "Hora"), ("ARRENDAMIENTO DE VOLQUETE POR VIAJE", "Viaje")], 420, (40, 600), "services"),
}

ENTITIES = [
    ("MUNICIPALIDAD DE VILLA ESPERANZA", "Gobiernos Locales (Municipalidades, Mancomunidades, etc.)", "Municipalidad"),
    ("MUNICIPALIDAD DE SAN MARCOS DEL VALLE", "Gobiernos Locales (Municipalidades, Mancomunidades, etc.)", "Municipalidad"),
    ("MUNICIPALIDAD DE SANTA CLARA", "Gobiernos Locales (Municipalidades, Mancomunidades, etc.)", "Municipalidad"),
    ("MUNICIPALIDAD DE LA LAGUNA", "Gobiernos Locales (Municipalidades, Mancomunidades, etc.)", "Municipalidad"),
    ("HOSPITAL REGIONAL DEL NORTE", "Entidades Descentralizadas y Autónomas", "Hospital"),
    ("HOSPITAL NACIONAL DE OCCIDENTE", "Entidades Descentralizadas y Autónomas", "Hospital"),
    ("CENTRO DE SALUD DE LA COSTA", "Gobierno Central", "Centro de salud"),
    ("MINISTERIO DE EJEMPLO, DIRECCIÓN ADMINISTRATIVA", "Gobierno Central", "Ministerio"),
    ("MINISTERIO DE INFRAESTRUCTURA DEMO", "Gobierno Central", "Ministerio"),
    ("UNIVERSIDAD ESTATAL DE EJEMPLO", "Entidades Descentralizadas y Autónomas", "Universidad"),
    ("INSTITUTO NACIONAL DE FOMENTO DEMO", "Empresas Públicas (Nacionales y Municipales)", "Instituto"),
    ("EMPRESA ELÉCTRICA MUNICIPAL DEMO", "Empresas Públicas (Nacionales y Municipales)", "Empresa pública"),
    ("DIRECCIÓN GENERAL DE CAMINOS DEMO", "Gobierno Central", "Dirección"),
    ("ESCUELA NORMAL DE EJEMPLO", "Gobierno Central", "Escuela"),
    ("POLICÍA MUNICIPAL DE TRÁNSITO DEMO", "Gobiernos Locales (Municipalidades, Mancomunidades, etc.)", "Policía"),
    ("INSTITUTO DE SEGURIDAD DEMO", "Entidades Descentralizadas y Autónomas", "Instituto"),
]

_PREFIX = ["COMERCIAL", "DISTRIBUIDORA", "SUMINISTROS", "INVERSIONES", "GRUPO", "SERVICIOS", "IMPORTADORA", "PROVEEDORA"]
_WORDS = ["ALFA", "BETA", "DELTA", "OMEGA", "SOLAR", "NORTE", "SUR", "ANDINA", "VOLCÁN", "QUETZAL", "CEIBA", "MAYA",
          "ATLAS", "NOVA", "PRISMA", "ÁGUILA", "TIKAL", "LAGO", "PACÍFICO", "ALTIPLANO", "ZENIT", "ORIÓN", "LUNA", "ROBLE"]
_SUFFIX = ["S.A.", "Y COMPAÑÍA LIMITADA", "S.A.", "SOCIEDAD ANÓNIMA"]


def _iso(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone(timedelta(hours=-6))).strftime("%Y-%m-%dT%H:%M:%S-06:00")


def _local(now: datetime, delta: timedelta) -> datetime:
    """`now` está en UTC naive; devuelve hora local de Guatemala (UTC-6) naive."""
    return now - timedelta(hours=6) + delta


def make_suppliers(rng: random.Random, n: int = 64) -> list[dict]:
    fams = list(FAMILIES)
    out: list[dict] = [{
        "id": DEMO_NIT, "name": DEMO_ORG_NAME, "fams": ["papel", "toner", "limpieza"], "disc": 1.0,
    }]
    used: set[str] = set()
    # Proveedores "semejantes" a la empresa demo: mismas familias base + otras (oportunidades)
    similar_extra = ["computo", "mobiliario", "llantas", "insumos_med", "pintura", "uniformes"]
    for i in range(n):
        while True:
            name = f"{rng.choice(_PREFIX)} {rng.choice(_WORDS)} {rng.choice(_SUFFIX)}"
            if name not in used:
                used.add(name)
                break
        if i < 14:
            f = rng.sample(["papel", "toner", "limpieza"], k=rng.choice([2, 3])) + rng.sample(similar_extra, k=2)
        else:
            f = rng.sample(fams, k=rng.choice([1, 2, 2, 3]))
        out.append({
            "id": f"GT-NIT-{rng.randint(1_000_000, 8_999_999)}", "name": name,
            "fams": f, "disc": rng.uniform(0.93, 1.06),
        })
    return out


def generate(now: datetime | None = None, seed: int = 42, n_historical: int = 900, n_open: int = 90) -> list[dict]:
    """Devuelve registros `{ocid, releases, compiledRelease}` como en los archivos mensuales."""
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    year_start = datetime(now.year, 1, 1)
    suppliers = make_suppliers(rng)
    by_fam: dict[str, list[dict]] = {}
    for s in suppliers:
        for f in s["fams"]:
            by_fam.setdefault(f, []).append(s)
    entities = []
    for i, (name, etype, level) in enumerate(ENTITIES):
        eid = f"GT-CISP-{21100000 + i * 37}"
        units = [(f"GT-GCUC-{10 + i}-{u}", f"{name.split(',')[0].title()} · Unidad {u}") for u in range(1, 4)]
        entities.append({"id": eid, "name": name, "etype": etype, "level": level, "units": units})

    records: list[dict] = []
    seq = 0
    total = n_historical + n_open
    for k in range(total):
        is_open = k >= n_historical
        seq += 1
        nog = 31_000_000 + seq * 7 + rng.randint(0, 5)
        if is_open:
            published = _local(now, -timedelta(days=rng.uniform(0.1, 11)))
            deadline = _local(now, timedelta(days=rng.uniform(0.5, 14)))
        else:
            span = max((now - year_start).days - 12, 30)
            published = year_start + timedelta(days=rng.uniform(0, span), hours=rng.uniform(7, 18))
            deadline = published + timedelta(days=rng.uniform(4, 14))
        fam_key = rng.choice(list(FAMILIES))
        code, variants, base, (qlo, qhi), category = FAMILIES[fam_key]
        n_items = 1 if rng.random() < 0.62 else rng.randint(2, 3)
        chosen = rng.sample(variants, k=min(n_items, len(variants)))
        qindex = (published.month - 1) // 3
        items, total_est = [], 0.0
        for j, (desc, unit) in enumerate(chosen):
            qty = int(math.exp(rng.uniform(math.log(qlo), math.log(qhi))))
            unit_price = base * (1 + 0.025 * qindex) * rng.lognormvariate(0, 0.07) * (1 + 0.25 * (j))
            items.append({
                "id": f"{rng.getrandbits(64):016X}", "description": desc,
                "classification": {"scheme": "UNSPSC", "id": code if j == 0 else code},
                "quantity": qty, "unit": {"name": unit},
                "attributes": [{"name": "Características", "value": desc.title(), "id": f"A{j}"}],
                "_unit_price": unit_price,
            })
            total_est += qty * unit_price
        if total_est < 90_000:
            method = "Compra Directa con Oferta Electrónica (Art. 43 LCE Inciso b)"
        elif total_est < 900_000:
            method = "Cotización (Art. 38 LCE)"
        else:
            method = "Licitación Pública (Art. 17 LCE)"

        ent = rng.choice(entities)
        unit_id, unit_name = rng.choice(ent["units"])
        title_variant = chosen[0][0].title()
        verb = rng.choice(["ADQUISICIÓN DE", "SUMINISTRO DE", "COMPRA DE", "SUMINISTRO Y ENTREGA DE"])
        if category == "services":
            verb = "SERVICIO DE"
        title = f"{verb} {chosen[0][0]}" + (" Y OTROS" if len(chosen) > 1 else "")

        candidates = by_fam.get(fam_key) or suppliers
        nb = 0 if is_open and rng.random() < 0.7 else rng.randint(1, min(6, len(candidates)))
        bidders = rng.sample(candidates, k=nb) if nb else []

        status, status_details = "active", "Vigente"
        awards, bids, contracts = [], [], []
        if not is_open:
            roll = rng.random()
            if not bidders or roll < 0.09:
                status, status_details, bidders = "unsuccessful", "Desierto", []
            elif roll < 0.12:
                status, status_details = "active", "Evaluación"
            else:
                status, status_details = "complete", "Adjudicado"
        if bidders:
            winner = min(bidders, key=lambda s: s["disc"] * rng.uniform(0.97, 1.03))
            award_total = sum(i["quantity"] * i["_unit_price"] for i in items) * winner["disc"]
            for bi, s in enumerate(bidders):
                amt = award_total * (1 if s is winner else rng.uniform(1.01, 1.28))
                bids.append({
                    "id": f"B{bi}", "date": _iso(published + timedelta(days=rng.uniform(1, 3))),
                    "status": "valid", "value": {"amount": round(amt, 2), "currency": "GTQ"},
                    "tenderers": [{"id": s["id"], "name": s["name"]}],
                })
            if status == "complete":
                adate = deadline + timedelta(days=rng.uniform(1, 9))
                awards.append({
                    "id": "1", "title": "Adjudicación", "status": "active", "statusDetails": "Adjudicado",
                    "date": _iso(adate), "value": {"amount": round(award_total, 2), "currency": "GTQ"},
                    "suppliers": [{"id": winner["id"], "name": winner["name"]}],
                })
                if rng.random() < 0.35:
                    contracts.append({
                        "id": "C1", "awardID": "1", "contractNumber": f"{rng.randint(1, 300)}-{now.year}",
                        "dateSigned": _iso(adate + timedelta(days=rng.uniform(3, 20))),
                        "value": {"amount": round(award_total, 2), "currency": "GTQ"},
                    })

        parties = [
            {"identifier": {"scheme": "GT-CISP", "id": ent["id"].split("-")[-1]},
             "address": {"region": "GUATEMALA", "countryName": "GUATEMALA"},
             "contactPoint": {"name": ent["name"]}, "roles": ["buyer"],
             "details": {"level": {"description": ent["level"], "id": "1"},
                         "entityType": {"description": ent["etype"], "id": "1"}, "type": {"description": "Sector Público", "id": "1"}},
             "id": ent["id"], "name": ent["name"]},
            {"identifier": {"scheme": "GT-GCUC", "id": unit_id.replace("GT-GCUC-", "")},
             "contactPoint": {"name": unit_name}, "roles": ["buyer"],
             "memberOf": [{"id": ent["id"], "name": ent["name"]}],
             "details": {"entityType": {"id": "0"}, "type": {"id": "0"}}, "id": unit_id, "name": unit_name},
        ]
        for s in bidders:
            roles = ["tenderer"] + (["supplier"] if awards and awards[0]["suppliers"][0]["id"] == s["id"] else [])
            parties.append({"identifier": {"scheme": "GT-NIT", "id": s["id"].replace("GT-NIT-", "")},
                            "roles": roles, "id": s["id"], "name": s["name"]})

        ocid = f"ocds-xqjsxa-{nog}"
        rel_date = _iso(published + timedelta(hours=rng.uniform(0, 30)))
        for it in items:
            it.pop("_unit_price")
        compiled = {
            "ocid": ocid, "date": rel_date, "publishedDate": rel_date, "language": "es",
            "tag": ["compiled"], "initiationType": "tender", "parties": parties,
            "buyer": {"id": ent["id"], "name": ent["name"]},
            "bids": {"details": bids},
            "tender": {
                "title": title, "status": status, "statusDetails": status_details,
                "datePublished": _iso(published),
                "procuringEntity": {"id": ent["id"], "name": ent["name"]},
                "items": items, "procurementMethod": "open", "procurementMethodDetails": method,
                "mainProcurementCategory": category, "submissionMethod": ["electronicSubmission"],
                "tenderPeriod": {"startDate": _iso(published), "endDate": _iso(deadline)},
                "numberOfTenderers": len(bidders),
                "tenderers": [{"id": s["id"], "name": s["name"]} for s in bidders],
                "documents": [{
                    "documentType": "purchaseRequest", "title": "Solicitud o requerimiento de bien, servicio o suministro",
                    "url": f"https://www.guatecompras.gt/concursos/consultaDetalleCon.aspx?nog={nog}&o=9",
                    "format": "text/html", "language": "es", "datePublished": _iso(published), "id": f"D{nog}",
                }],
                "id": f"GT-NOG-{nog}",
            },
            "awards": awards, "contracts": contracts,
            "sources": [{"url": "https://www.guatecompras.gt", "id": "GUATECOMPRAS", "name": "DEMO"}],
        }
        records.append({
            "ocid": ocid,
            "releases": [{"url": f"https://ocds.guatecompras.gt/release/GT-NOG-{nog}-T0", "date": rel_date,
                          "tag": ["tender"] + (["award"] if awards else [])}],
            "compiledRelease": compiled,
        })
    return records
