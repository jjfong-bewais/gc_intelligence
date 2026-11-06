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
    u.add_argument("--role", default="admin"); u.add_argument("--nit", action="append", default=[])
    i = sub.add_parser("ingest", help="descarga e importa archivos mensuales de Guatecompras")
    i.add_argument("--months-back", type=int, default=2, help="0 = todo el año")
    i.add_argument("--only", nargs="*", help="p. ej. 2026-09 2026-10")
    i.add_argument("--force", action="store_true")
    i.add_argument("--no-embed", action="store_true")
    e = sub.add_parser("embed", help="calcula embeddings pendientes")
    e.add_argument("--limit", type=int)
    a = sub.add_parser("alerts", help="envía alertas pendientes")
    a.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    from .db import engine
    if a.cmd == "init-db":
        from .schema import init_db
        init_db(); print("OK")
    elif a.cmd == "demo":
        from .demo.seed import seed_demo
        seed_demo(a.historical, a.open, a.reset)
    elif a.cmd == "create-user":
        from .models import app_user, org_supplier, organization
        from .schema import init_db
        from .security import hash_password
        init_db()
        with engine.begin() as c:
            org = c.execute(sa.insert(organization).values(name=a.org or a.email)).inserted_primary_key[0]
            for n in a.nit:
                c.execute(sa.insert(org_supplier).values(org_id=org, supplier_id=n if n.startswith("GT-NIT-") else f"GT-NIT-{n}"))
            c.execute(sa.insert(app_user).values(org_id=org, email=a.email.lower(), name=a.name, role=a.role,
                                                 password_hash=hash_password(a.password)))
        print("Usuario creado")
    elif a.cmd == "ingest":
        from .ingest.sync import sync
        from .schema import init_db
        from .services.embeddings import embed_pending
        init_db()
        sync(months_back=a.months_back, only=a.only, force=a.force)
        if not a.no_embed:
            with engine.begin() as c:
                print(embed_pending(c))
    elif a.cmd == "embed":
        from .services.embeddings import embed_pending
        with engine.begin() as c:
            print(embed_pending(c, a.limit))
    elif a.cmd == "alerts":
        from .services.alerts import run_all
        with engine.begin() as c:
            print(run_all(c, a.force))
    return 0


if __name__ == "__main__":
    sys.exit(main())
