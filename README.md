# GC Intelligence

Inteligencia de mercado sobre las compras públicas de Guatemala (API OCDS de Guatecompras):

- Búsqueda de concursos por palabras clave, similitud semántica o híbrida.
- Comparación de concursos vigentes con adjudicaciones pasadas (precios unitarios, tendencia, concursos parecidos).
- Recomendaciones: concursos vigentes parecidos a lo que tus NIT ganaron/cotizaron, ajustadas con 👍/👎.
- Oportunidades: productos donde participan proveedores semejantes y tú no.
- Cruce con inventario (CSV) y alertas por correo con búsquedas guardadas, favoritos y feedback.

Stack: FastAPI + SQLAlchemy Core · Postgres + pgvector (SQLite en la demo) · React/Vite/Tailwind · GitHub Actions (ingesta) · Resend · OpenAI embeddings.

## Demo local (5 minutos, todo dentro del repo)

```bash
./scripts/demo.sh        # crea .venv (y .node si falta Node), datos sintéticos, API + UI
# → http://localhost:8000   demo@gcintelligence.local / demo1234
```

Requisitos: Python ≥ 3.10 y acceso a internet para instalar paquetes. Si no hay Node ≥ 18 se instala uno local en `.node/`.
La demo usa SQLite, embeddings locales (sin red) y guarda los correos en `demo/outbox/`. **Los datos son sintéticos.**

Otros comandos: `make setup`, `make test`, `make dev-api` + `make dev-web` (UI con recarga en :5173).

## Nube

Ver [docs/DEPLOY.md](docs/DEPLOY.md): Neon (DB) + Fly.io (API) + Cloudflare Pages (web) + GitHub Actions (ingesta/alertas) + Resend (correo). ~US$10–20/mes.

## Estructura

```
backend/app/  config, db, models, schema · ingest/ (cliente, parser, loader, sync) · services/ (búsqueda, vectores,
              comparables, recomendaciones, oportunidades, inventario, alertas, correo) · routers/ · demo/ · cli.py
backend/tests/  pytest (SQLite; Postgres con TEST_DATABASE_URL)
frontend/       React + TS + Tailwind + TanStack Query + Recharts
.github/workflows/  ci, ingest (cron diario), deploy-api
```

CLI: `cd backend && ../.venv/bin/python -m app.cli --help` (init-db, create-user, set-role, ingest, embed, alerts, demo).

Roles: `member` (toda la plataforma) y `admin` (además crea, edita, desactiva y elimina usuarios y ve las operaciones globales). Los permisos viven en `backend/app/permissions.py`: los endpoints piden `require(Perm.X)`, así que dar o quitar funciones por usuario no requiere tocar código (`perm_overrides`).

## Métricas de uso (administradores)

Menú **Administración → Métricas de uso** (permiso `admin`): usuarios activos (DAU/WAU/MAU), sesiones (duración y tiempo activo), mapa de calor de horarios, uso y adopción por función, embudo búsqueda → concurso → seguimiento, búsquedas (texto, modos, filtros, sin resultados), ranking y estado de cada usuario (activo / en riesgo / dormido), retención semanal y salud técnica (errores y latencia). Por defecto no cuentan los administradores (hay un interruptor).

- Captura: un middleware (`services/usage.py`) registra cada llamada a la API en `usage_event` por lotes y en segundo plano; el navegador manda pantallas vistas y tiempo activo a `POST /api/v1/telemetry` (`frontend/src/telemetry.ts`). Una **sesión** termina tras 30 min sin actividad.
- Consultas: `services/metrics.py` y `routers/metrics.py` (`/api/v1/admin/metrics/*`).
- Se guarda el texto completo de las búsquedas (la Guía avisa a los usuarios). Retención: 90 días (`USAGE_RETENTION_DAYS`); `python -m app.cli prune-usage` borra lo vencido y corre en el workflow diario.
- Días y horas se agrupan en hora de Guatemala (`METRICS_TZ_OFFSET=-6`).

## Notas

- La ingesta lee los ZIP mensuales de `https://ocds.guatecompras.gt` (≈230 MB JSON cada uno) en streaming y revisa siempre los 2 últimos meses (las adjudicaciones tardías reescriben el archivo del mes de la convocatoria).
- Los precios unitarios solo se derivan de concursos de 1 renglón con 1 adjudicación.
- Calibra `MATCH_THRESHOLD` con datos reales cuando cambies de modelo de embeddings.
