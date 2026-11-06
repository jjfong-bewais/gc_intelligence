from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import settings
from .routers import auth, insights, misc, suppliers, tenders, workspace
from .schema import init_db

log = logging.getLogger("gc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()  # idempotente
    except Exception:  # la base puede estar despertando (Neon); el healthcheck lo mostrará
        log.exception("init_db falló")
    yield


app = FastAPI(title="GC Intelligence", version=__version__, lifespan=lifespan)
if settings.cors_list:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

api = APIRouter(prefix="/api/v1")
for r in (auth.router, tenders.router, suppliers.router, insights.router, workspace.router, misc.router):
    api.include_router(r)
app.include_router(api)

dist = Path(settings.frontend_dist)
if dist.is_dir() and (dist / "index.html").exists():  # demo local / despliegue todo-en-uno
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (dist / path).resolve()
        if path and f.is_file() and dist.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(dist / "index.html")
