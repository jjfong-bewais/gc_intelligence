"""Motor de base de datos y tipo de vector portable (SQLite demo / Postgres + pgvector)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import numpy as np
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.types import TypeDecorator

from .config import settings


def utcnow() -> datetime:
    """Fecha y hora UTC sin zona horaria (así se guarda todo en la base)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Vec(TypeDecorator):
    """Vector de embeddings: pgvector en Postgres, bytes float32 en SQLite."""

    impl = sa.LargeBinary
    cache_ok = True

    def __init__(self, dim: int, kind: str = "vector") -> None:
        super().__init__()
        self.dim = dim
        self.kind = kind

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import HALFVEC, VECTOR

            cls = HALFVEC if self.kind == "halfvec" else VECTOR
            return dialect.type_descriptor(cls(self.dim))
        return dialect.type_descriptor(sa.LargeBinary())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        arr = np.asarray(value, dtype=np.float32)
        if dialect.name == "postgresql":
            return arr.tolist()
        return arr.tobytes()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray, memoryview)):
            return np.frombuffer(bytes(value), dtype=np.float32)
        if hasattr(value, "to_numpy"):
            return np.asarray(value.to_numpy(), dtype=np.float32)
        return np.asarray(value, dtype=np.float32)

    @property
    def python_type(self):  # pragma: no cover
        return np.ndarray


def _make_engine() -> sa.Engine:
    url = settings.sqlalchemy_url
    if settings.is_sqlite:
        path = url.replace("sqlite:///", "", 1)
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        eng = sa.create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _pragmas(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()

        return eng
    # Neon suspende el cómputo al estar inactivo: pre-ping y reciclaje evitan conexiones muertas.
    return sa.create_engine(
        url, pool_pre_ping=True, pool_recycle=240, pool_size=5, max_overflow=5
    )


engine = _make_engine()
IS_PG = engine.dialect.name == "postgresql"


def get_conn() -> Iterator[sa.Connection]:
    """Dependencia de FastAPI: una conexión con transacción por petición."""
    with engine.begin() as conn:
        yield conn
