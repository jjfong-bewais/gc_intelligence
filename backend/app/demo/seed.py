"""Datos de demostración (sintéticos): concursos, usuario demo, inventario y búsqueda guardada."""
from __future__ import annotations

import csv
import io

import sqlalchemy as sa

from ..db import engine, utcnow
from ..ingest.loader import load_records
from ..models import app_user, org_supplier, organization, saved_search, tender
from ..schema import init_db
from ..security import hash_password
from ..services.embeddings import embed_pending
from ..services.inventory import import_inventory, parse_csv
from ..services.opportunities import clear_cache
from .generator import DEMO_NIT, DEMO_ORG_NAME, generate

DEMO_EMAIL = "demo@gcintelligence.local"
DEMO_PASSWORD = "demo1234"

INVENTORY_CSV = """sku,descripcion,unidad,unspsc
PAP-001,Papel bond tamaño carta 75 g resma de 500 hojas,resma,14111507
PAP-002,Papel bond tamaño oficio 75 g resma,resma,14111507
TON-010,Tóner compatible para impresora láser negro,unidad,44103103
TON-011,Cartucho de tinta negro para impresora,unidad,44103105
LIM-020,Desinfectante líquido multiusos galón,galón,47131800
LIM-021,Cloro líquido galón,galón,47131800
LIM-022,Papel higiénico jumbo rollo,paquete,14111704
CUA-030,Cuadernos espiral de 100 hojas,unidad,44121706
"""


def seed_demo(n_historical: int = 900, n_open: int = 90, reset: bool = False, log=print) -> None:
    init_db()
    with engine.connect() as c:
        have = c.execute(sa.select(sa.func.count()).select_from(tender)).scalar()
    if have and not reset:
        log(f"La base ya tiene {have} concursos; usa --reset para regenerar.")
        return
    if reset:
        from ..schema import drop_all
        drop_all()
        init_db()
    log("Generando datos sintéticos…")
    stats = load_records(generate(n_historical=n_historical, n_open=n_open), {})
    log(f"  {stats.inserted} concursos cargados")
    with engine.begin() as conn:
        log("Calculando embeddings…")
        log(f"  {embed_pending(conn)}")
        org = conn.execute(sa.insert(organization).values(name=DEMO_ORG_NAME)).inserted_primary_key[0]
        conn.execute(sa.insert(org_supplier).values(org_id=org, supplier_id=DEMO_NIT))
        uid = conn.execute(sa.insert(app_user).values(
            org_id=org, email=DEMO_EMAIL, name="Usuario Demo", role="admin", password_hash=hash_password(DEMO_PASSWORD)
        )).inserted_primary_key[0]
        import_inventory(conn, org, parse_csv(INVENTORY_CSV))
        conn.execute(sa.insert(saved_search).values(
            user_id=uid, name="Papel y tóner vigentes", q="papel bond tóner impresora", mode="hybrid",
            filters={"status": "open"}, frequency="daily", active=True, last_run_at=None, created_at=utcnow()))
    clear_cache()
    log(f"Listo. Ingresa con {DEMO_EMAIL} / {DEMO_PASSWORD}")
