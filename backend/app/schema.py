"""Creación del esquema e índices (extensiones e índices específicos de Postgres)."""
from __future__ import annotations

import sqlalchemy as sa

from .config import settings
from .db import IS_PG, engine
from .models import metadata, tender

# Columnas agregadas después de la primera versión: (tabla, columna, DDL).
NEW_COLUMNS = [
    ("tender", "buyer_region", "VARCHAR(120)"),
    ("tender", "buyer_type", "VARCHAR(120)"),
    ("saved_search", "max_items", "INTEGER NOT NULL DEFAULT 5"),
]


def _migrate() -> None:
    """Agrega columnas e índices nuevos a bases existentes (create_all no altera tablas)."""
    with engine.begin() as conn:
        insp = sa.inspect(conn)
        added = set()
        for table, col, ddl in NEW_COLUMNS:
            if col not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                added.add(col)
        if "buyer_region" in added or "buyer_type" in added:
            backfill_buyer_fields(conn)
        have = {i["name"] for i in sa.inspect(conn).get_indexes("tender")}
        for ix in tender.indexes:
            if ix.name not in have:
                ix.create(conn)


def backfill_buyer_fields(conn: sa.Connection) -> None:
    """Copia departamento y tipo de entidad desde `party` a los concursos ya cargados."""
    if IS_PG:
        conn.execute(sa.text(
            "UPDATE tender t SET buyer_region = p.region, buyer_type = p.entity_type "
            "FROM party p WHERE p.id = t.buyer_id AND (t.buyer_region IS NULL OR t.buyer_type IS NULL)"))
    else:
        conn.execute(sa.text(
            "UPDATE tender SET buyer_region = (SELECT region FROM party WHERE party.id = tender.buyer_id), "
            "buyer_type = (SELECT entity_type FROM party WHERE party.id = tender.buyer_id) "
            "WHERE buyer_region IS NULL OR buyer_type IS NULL"))


def init_db() -> None:
    if IS_PG:
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    metadata.create_all(engine)
    _migrate()
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
