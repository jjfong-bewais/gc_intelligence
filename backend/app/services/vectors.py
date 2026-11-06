"""Búsqueda por vecinos más cercanos: pgvector en Postgres, fuerza bruta (numpy) en SQLite."""
from __future__ import annotations

import numpy as np
import sqlalchemy as sa

from ..config import settings
from ..db import Vec

MAX_BRUTE_ROWS = 200_000
_GUC_OK: dict[str, bool] = {}


def _set_guc(conn: sa.Connection, name: str, value: str) -> None:
    """Ajusta un parámetro de pgvector si existe en esta versión (iterative_scan: >= 0.8)."""
    if _GUC_OK.get(name) is False:
        return
    try:
        with conn.begin_nested():
            conn.execute(sa.text("SELECT set_config(:n, :v, true)"), {"n": name, "v": value})
        _GUC_OK[name] = True
    except Exception:
        _GUC_OK[name] = False


def _qvec(vec: np.ndarray):
    return sa.cast(np.asarray(vec, dtype=np.float32), Vec(settings.embedding_dim, settings.pgvector_type))


def vector_search(
    conn: sa.Connection, table: sa.Table, key: sa.ColumnElement, q: np.ndarray, k: int,
    conds: tuple | list = (),
) -> list[tuple[str, float]]:
    """Devuelve [(clave, similitud coseno)] de mayor a menor."""
    emb = table.c.embedding
    if conn.dialect.name == "postgresql":
        dist = emb.op("<=>", return_type=sa.Float)(_qvec(q))
        _set_guc(conn, "hnsw.iterative_scan", "relaxed_order")
        _set_guc(conn, "hnsw.ef_search", "100")
        rows = conn.execute(
            sa.select(key, dist.label("d")).where(emb.is_not(None), *conds).order_by(dist).limit(k)
        ).all()
        return [(r[0], 1.0 - float(r[1])) for r in rows]
    rows = conn.execute(
        sa.select(key, emb).where(emb.is_not(None), *conds).limit(MAX_BRUTE_ROWS)
    ).all()
    if not rows:
        return []
    mat = np.stack([r[1] for r in rows])
    sims = mat @ np.asarray(q, dtype=np.float32)
    order = np.argsort(-sims)[:k]
    return [(rows[i][0], float(sims[i])) for i in order]


def fetch_vectors(
    conn: sa.Connection, table: sa.Table, key: sa.ColumnElement, ids: list[str]
) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        for k, v in conn.execute(
            sa.select(key, table.c.embedding).where(key.in_(chunk), table.c.embedding.is_not(None))
        ):
            out[k] = v
    return out


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Similitud coseno entre filas ya normalizadas."""
    return a @ b.T
