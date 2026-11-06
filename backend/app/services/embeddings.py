"""Embeddings detrás de una interfaz: 'local' (demo, sin red) u 'openai'."""
from __future__ import annotations

import time
import zlib
from functools import lru_cache

import httpx
import numpy as np
import sqlalchemy as sa

from ..config import settings
from ..models import inventory_item, tender, tender_item
from .text import normalize, sha1


def _unit(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (mat / norms).astype(np.float32)


class LocalHashEmbedder:
    """Embedding léxico determinista (n-gramas de caracteres + palabras con hashing).

    Sirve para la demo sin claves ni red. No capta sinónimos: para similitud
    semántica real use EMBEDDINGS_PROVIDER=openai.
    """

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.signature = f"local:hash:{dim}"

    @staticmethod
    def _stem(w: str) -> str:
        if len(w) > 5 and w.endswith("es"):
            return w[:-2]
        if len(w) > 4 and w.endswith("s"):
            return w[:-1]
        return w

    def _add(self, row: np.ndarray, feat: str, weight: float) -> None:
        h = zlib.crc32(feat.encode("utf-8"))
        sign = 1.0 if (h >> 31) & 1 else -1.0
        row[h % self.dim] += sign * weight

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in normalize(t).split():
                w = self._stem(w)
                self._add(out[i], "w:" + w, 1.0)
                padded = f" {w} "
                for n in (3, 4):
                    for j in range(len(padded) - n + 1):
                        self._add(out[i], "g:" + padded[j:j + n], 0.35)
        return _unit(out)


class OpenAIEmbedder:
    def __init__(self, dim: int, model: str, api_key: str) -> None:
        if not api_key:
            raise RuntimeError("Falta OPENAI_API_KEY para EMBEDDINGS_PROVIDER=openai")
        self.dim, self.model, self.api_key = dim, model, api_key
        self.signature = f"openai:{model}:{dim}"

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 256):
            batch = [t[:6000] or " " for t in texts[start:start + 256]]
            vectors.extend(self._call(batch))
        return _unit(np.asarray(vectors, dtype=np.float32))

    def _call(self, batch: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": batch, "dimensions": self.dim}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for attempt in range(5):
            try:
                r = httpx.post(
                    "https://api.openai.com/v1/embeddings", json=payload,
                    headers=headers, timeout=90,
                )
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError("reintentable", request=r.request, response=r)
                r.raise_for_status()
                data = sorted(r.json()["data"], key=lambda d: d["index"])
                return [d["embedding"] for d in data]
            except (httpx.HTTPError, KeyError):
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        return []  # pragma: no cover


@lru_cache
def get_embedder():
    if settings.embeddings_provider == "openai":
        return OpenAIEmbedder(
            settings.embedding_dim, settings.openai_embedding_model, settings.openai_api_key
        )
    return LocalHashEmbedder(settings.embedding_dim)


def embed_query(text: str) -> np.ndarray:
    return get_embedder().embed([text])[0]


def embed_pending(conn: sa.Connection, limit: int | None = None, batch: int = 256) -> dict[str, int]:
    """Calcula los vectores que faltan o cambiaron (texto nuevo o modelo distinto)."""
    emb = get_embedder()
    sig = emb.signature
    done = {"tender": 0, "tender_item": 0, "inventory_item": 0}
    jobs = [
        ("tender", tender, tender.c.ocid, tender.c.published_at.desc()),
        ("tender_item", tender_item, tender_item.c.id, tender_item.c.idx),
    ]
    for name, table, key, order in jobs:
        while limit is None or done[name] < limit:
            need = sa.or_(
                table.c.embedding.is_(None),
                table.c.emb_sig.is_(None),
                table.c.emb_sig != sig,
                table.c.emb_hash.is_(None),
                table.c.emb_hash != table.c.text_hash,
            )
            rows = conn.execute(
                sa.select(key, table.c.embed_text, table.c.text_hash)
                .where(need, table.c.embed_text != "")
                .order_by(order)
                .limit(batch)
            ).all()
            if not rows:
                break
            vecs = emb.embed([r[1] for r in rows])
            conn.execute(
                sa.update(table).where(key == sa.bindparam("k")).values(
                    embedding=sa.bindparam("v"), emb_hash=sa.bindparam("h"), emb_sig=sig
                ),
                [{"k": r[0], "v": vecs[i], "h": r[2]} for i, r in enumerate(rows)],
            )
            done[name] += len(rows)
    done["inventory_item"] = embed_inventory(conn)
    return done


def embed_inventory(conn: sa.Connection) -> int:
    emb = get_embedder()
    sig = emb.signature
    rows = conn.execute(
        sa.select(inventory_item.c.id, inventory_item.c.description).where(
            sa.or_(inventory_item.c.embedding.is_(None), inventory_item.c.emb_sig != sig)
        )
    ).all()
    for start in range(0, len(rows), 256):
        chunk = rows[start:start + 256]
        vecs = emb.embed([r[1] for r in chunk])
        conn.execute(
            sa.update(inventory_item).where(inventory_item.c.id == sa.bindparam("k")).values(
                embedding=sa.bindparam("v"), emb_sig=sig
            ),
            [{"k": r[0], "v": vecs[i]} for i, r in enumerate(chunk)],
        )
    return len(rows)


def text_hash(text: str) -> str:
    return sha1(text)
