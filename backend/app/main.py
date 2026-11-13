from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import settings
from .routers import auth, buyers, insights, metrics, misc, suppliers, tenders, users, workspace
from .schema import init_db
from .services import usage
from .services.users import UserError

log = logging.getLogger("uvicorn.error")  # sale en los logs de Fly


def _init_db_background() -> None:
    try:
        init_db(heavy=False)  # idempotente; rellenos e índices grandes los hace la ingesta (CLI)
        log.info("init_db listo")
    except Exception:  # la base puede estar despertando (Neon); el healthcheck lo mostrará
        log.exception("init_db falló")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # En un hilo aparte: uvicorn no abre el puerto hasta que termina el arranque, y si la base
    # tarda (Neon despertando, candados de la ingesta) Fly da la máquina por caída.
    threading.Thread(target=_init_db_background, name="init-db", daemon=True).start()
    usage.ensure_started()
    yield
    usage.stop()  # vacía la cola de métricas antes de apagar


app = FastAPI(title="GC Intelligence", version=__version__, lifespan=lifespan)
app.add_middleware(usage.UsageMiddleware)
if settings.cors_list:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])



@app.exception_handler(UserError)
async def _user_error(_: Request, e: UserError):
    return JSONResponse({"detail": str(e)}, status_code=e.status)


api = APIRouter(prefix="/api/v1")
for r in (auth.router, users.router, tenders.router, suppliers.router, buyers.router, insights.router, workspace.router, misc.router, metrics.router):
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
