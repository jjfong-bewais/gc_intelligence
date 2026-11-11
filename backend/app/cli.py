"""Línea de comandos:  python -m app.cli <comando>"""
from __future__ import annotations

import argparse
import sys

import sqlalchemy as sa


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gc", description="GC Intelligence")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="crea tablas e índices")
    d = sub.add_parser("demo", help="carga datos sintéticos y usuario demo")
    d.add_argument("--reset", action="store_true")
    d.add_argument("--historical", type=int, default=900)
    d.add_argument("--open", type=int, default=90)
    u = sub.add_parser("create-user", help="crea organización y usuario")
    u.add_argument("email"); u.add_argument("password")
    u.add_argument("--name", default=""); u.add_argument("--org", default="")
    u.add_argument("--role", default="member", choices=["member", "admin"])
    u.add_argument("--nit", action="append", default=[])
    r = sub.add_parser("set-role", help="cambia el rol de un usuario (member | admin)")
    r.add_argument("email"); r.add_argument("role", choices=["member", "admin"])
    i = sub.add_parser("ingest", help="descarga e importa archivos mensuales de Guatecompras")
    i.add_argument("--months-back", type=int, default=2, help="0 = todo el año")
    i.add_argument("--only", nargs="*", help="p. ej. 2026-09 2026-10")
    i.add_argument("--from", dest="since", help="primer mes a cargar AAAA-MM (por defecto DATA_FROM=2024-01)")
    i.add_argument("--force", action="store_true")
    i.add_argument("--no-embed", action="store_true")
    e = sub.add_parser("embed", help="calcula embeddings pendientes")
    e.add_argument("--limit", type=int)
    a = sub.add_parser("alerts", help="envía alertas pendientes")
    a.add_argument("--force", action="store_true")
    pu = sub.add_parser("prune-usage", help="borra eventos de uso más viejos que USAGE_RETENTION_DAYS (90)")
    pu.add_argument("--days", type=int)
    a = ap.parse_args(argv)

    from .db import engine
    if a.cmd == "init-db":
        from .schema import init_db
        init_db(); print("OK")
    elif a.cmd == "demo":
        from .demo.seed import seed_demo
        seed_demo(a.historical, a.open, a.reset)
    elif a.cmd == "create-user":
        from .schema import init_db
        from .services.users import UserError, create_user
        init_db()
        nits = tuple(n if n.startswith("GT-NIT-") else f"GT-NIT-{n}" for n in a.nit)
        try:
            with engine.begin() as c:
                create_user(c, email=a.email, name=a.name, company=a.org, role=a.role, password=a.password, nits=nits)
        except UserError as e:
            print(f"Error: {e}"); return 1
        print("Usuario creado")
    elif a.cmd == "set-role":
        from .models import app_user
        with engine.begin() as c:
            n = c.execute(sa.update(app_user).where(app_user.c.email == a.email.strip().lower()).values(role=a.role)).rowcount
        print("Rol actualizado" if n else "No existe ese usuario")
    elif a.cmd == "ingest":
        from .ingest.sync import sync
        from .schema import init_db
        from .services.embeddings import embed_pending
        init_db()
        sync(months_back=a.months_back, only=a.only, force=a.force, since=a.since)
        if not a.no_embed:
            with engine.begin() as c:
                print(embed_pending(c))
    elif a.cmd == "embed":
        from .services.embeddings import embed_pending
        with engine.begin() as c:
            print(embed_pending(c, a.limit))
    elif a.cmd == "prune-usage":
        from .services.usage import prune
        with engine.begin() as c:
            print(prune(c, a.days))
    elif a.cmd == "alerts":
        from .services.alerts import run_all
        with engine.begin() as c:
            print(run_all(c, a.force))
    return 0


if __name__ == "__main__":
    sys.exit(main())
