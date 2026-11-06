"""Cliente del API OCDS de Guatecompras (archivos mensuales)."""
from __future__ import annotations

import tempfile
import time
import zipfile
from pathlib import Path
from typing import Iterator

import httpx
import ijson

from ..config import settings

USER_AGENT = "gc-intelligence/0.1 (+https://github.com/jjfong-bewais/gc_intelligence)"


class GuatecomprasClient:
    def __init__(self, base: str | None = None) -> None:
        self.base = (base or settings.guatecompras_base).rstrip("/")
        self.http = httpx.Client(
            headers={"User-Agent": USER_AGENT}, follow_redirects=True,
            timeout=httpx.Timeout(60.0, read=900.0),
        )

    def list_files(self, year: int) -> list[dict]:
        """GET /files?year=Y -> [{id, year, month, timestamp, files:{json,csv,xlsx,sha}}]."""
        r = self._get(f"{self.base}/files", params={"year": year})
        return sorted(r.json().get("result", []), key=lambda f: (f["year"], f["month"]))

    def download(self, url: str, dest_dir: str | None = None) -> Path:
        """Descarga en streaming un archivo mensual (ZIP) a disco, con reintentos."""
        dest = Path(dest_dir or tempfile.mkdtemp(prefix="gc_")) / url.rstrip("/").replace("/", "_")
        last: Exception | None = None
        for attempt in range(4):
            try:
                with self.http.stream("GET", url) as r:
                    r.raise_for_status()
                    with open(dest, "wb") as fh:
                        for chunk in r.iter_bytes(1 << 20):
                            fh.write(chunk)
                return dest
            except httpx.HTTPError as exc:  # el colector de OCP también reintenta los 400
                last = exc
                time.sleep(2 ** (attempt + 1))
        raise RuntimeError(f"No se pudo descargar {url}: {last}")

    def _get(self, url: str, **kw) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(4):
            try:
                r = self.http.get(url, **kw)
                r.raise_for_status()
                return r
            except httpx.HTTPError as exc:
                last = exc
                time.sleep(2 ** (attempt + 1))
        raise RuntimeError(f"Fallo al consultar {url}: {last}")


def iter_zip_records(path: str | Path) -> Iterator[dict]:
    """Lee `records.item` del JSON dentro del ZIP en streaming (el archivo pesa ~230 MB)."""
    with zipfile.ZipFile(path) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".json"))
        with zf.open(name) as fh:
            yield from ijson.items(fh, "records.item", use_float=True)
