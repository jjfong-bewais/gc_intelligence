"""Creación del esquema e índices (extensiones e índices específicos de Postgres)."""
from __future__ import annotations

import sqlalchemy as sa

from .config import settings
from .db import IS_PG, engine
from .models import metadata


def init_db() -> None:
    if IS_PG:
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    metadata.create_all(engine)
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
