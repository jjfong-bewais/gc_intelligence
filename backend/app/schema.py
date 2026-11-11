"""Creación del esquema e índices (extensiones e índices específicos de Postgres)."""
from __future__ import annotations

import logging
import time

import sqlalchemy as sa

from .config import settings
from .db import IS_PG, engine
from .models import metadata, tender

log = logging.getLogger("uvicorn.error")  # sale en los logs de Fly

# Columnas agregadas después de la primera versión: (tabla, columna, DDL).
NEW_COLUMNS = [
    ("tender", "buyer_region", "VARCHAR(120)"),
    ("tender", "buyer_type", "VARCHAR(120)"),
    ("saved_search", "max_items", "INTEGER NOT NULL DEFAULT 5"),
    ("org_supplier", "label", "VARCHAR(200) NOT NULL DEFAULT ''"),
    ("app_user", "active", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("app_user", "must_change_password", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("app_user", "perm_overrides", "JSON"),
]


def _add_columns(attempts: int = 10) -> None:
    """Una transacción corta por columna (si no, el ALTER de una tabla queda esperando a otra
    mientras las peticiones leen ambas: deadlock). Reintenta si la tabla está ocupada."""
    for table, col, ddl in NEW_COLUMNS:
        for i in range(attempts):
            try:
                with engine.begin() as conn:
                    if col in {c["name"] for c in sa.inspect(conn).get_columns(table)}:
                        break
                    if IS_PG:
                        conn.execute(sa.text("SET LOCAL lock_timeout = '3s'"))
                        conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ddl}"))
                    else:
                        conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                log.warning("migración: columna %s.%s agregada", table, col)
                break
            except sa.exc.OperationalError as e:  # lock_timeout o deadlock: reintentar
                if i == attempts - 1:
                    raise
                log.warning("migración: %s.%s ocupada (%s); reintento %d", table, col, type(e.orig).__name__, i + 1)
                time.sleep(2 + i)


def _migrate(heavy: bool) -> None:
    """Agrega columnas nuevas a bases existentes (create_all no altera tablas).
    Agregar una columna nula es instantáneo; con `heavy` además rellena datos y crea índices
    sobre `tender`, lo que en producción tarda: se hace en la ingesta (CLI), no al arrancar la API."""
    _add_columns()
    if not heavy:
        return
    backfill_buyer_fields()
    with engine.begin() as conn:
        have = {i["name"] for i in sa.inspect(conn).get_indexes("tender")}
        for ix in tender.indexes:
            if ix.name not in have:
                ix.create(conn)


BACKFILL_BATCH = 20_000


def backfill_buyer_fields() -> int:
    """Copia departamento y tipo de entidad desde `party` a los concursos que aún no los tienen.
    Por lotes (una transacción cada uno) para no bloquear la tabla. Devuelve filas actualizadas."""
    pending = (
        "SELECT t2.ocid FROM tender t2 JOIN party p2 ON p2.id = t2.buyer_id "
        "WHERE (t2.buyer_region IS NULL AND p2.region IS NOT NULL) "
        "OR (t2.buyer_type IS NULL AND p2.entity_type IS NOT NULL) LIMIT :n"
    )
    if IS_PG:
        sql = ("UPDATE tender t SET buyer_region = COALESCE(t.buyer_region, p.region), "
               "buyer_type = COALESCE(t.buyer_type, p.entity_type) FROM party p "
               f"WHERE p.id = t.buyer_id AND t.ocid IN ({pending})")
    else:
        sql = ("UPDATE tender SET "
               "buyer_region = COALESCE(buyer_region, (SELECT region FROM party WHERE party.id = tender.buyer_id)), "
               "buyer_type = COALESCE(buyer_type, (SELECT entity_type FROM party WHERE party.id = tender.buyer_id)) "
               f"WHERE ocid IN ({pending})")
    total = 0
    while True:
        with engine.begin() as conn:
            n = conn.execute(sa.text(sql), {"n": BACKFILL_BATCH}).rowcount or 0
        total += n
        if n < BACKFILL_BATCH:
            return total


def init_db(heavy: bool = True) -> None:
    """Idempotente. `heavy=False` (arranque de la API): solo lo instantáneo, para que el
    servidor escuche de inmediato y pase el healthcheck de Fly."""
    if IS_PG:
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    metadata.create_all(engine)
    _migrate(heavy)
    if IS_PG:
        ops = "halfvec_cosine_ops" if settings.pgvector_type == "halfvec" else "vector_cosine_ops"
        stmts = [
            "CREATE INDEX IF NOT EXISTS ix_tender_search_trgm ON tender USING gin (search_text gin_trgm_ops)",
            "CREATE INDEX IF NOT EXISTS ix_party_name_trgm ON party USING gin (name_norm gin_trgm_ops)",
            f"CREATE INDEX IF NOT EXISTS ix_tender_emb_hnsw ON tender USING hnsw (embedding {ops})",
            f"CREATE INDEX IF NOT EXISTS ix_item_emb_hnsw ON tender_item USING hnsw (embedding {ops})",
        ]
        # CREATE INDEX IF NOT EXISTS toma un candado que bloquea escrituras aunque el índice ya
        # exista (y provoca deadlocks con la ingesta): solo se ejecuta si el índice falta.
        with engine.begin() as conn:
            have = set(conn.execute(sa.text("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")).scalars())
            for s in stmts:
                name = s.split("IF NOT EXISTS ")[1].split(" ")[0]
                if name not in have:
                    conn.execute(sa.text(s))


def drop_all() -> None:
    metadata.drop_all(engine)
