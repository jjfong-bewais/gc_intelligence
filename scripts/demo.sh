#!/usr/bin/env bash
# Demo local completa: datos sintéticos + API + interfaz en http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x .venv/bin/python ] || ./scripts/setup.sh
[ -d .node/bin ] && export PATH="$PWD/.node/bin:$PATH"

export GC_MODE=demo MAIL_PROVIDER=file EMBEDDINGS_PROVIDER=local
export DATABASE_URL="sqlite:///$PWD/demo/demo.db"
export OUTBOX_DIR="$PWD/demo/outbox"
export SECRET_KEY="${SECRET_KEY:-demo-secret-not-for-production}"
PORT="${PORT:-8000}"; export APP_URL="http://localhost:$PORT"

if [ ! -f frontend/dist/index.html ]; then
  [ -d frontend/node_modules ] || (cd frontend && npm install --no-audit --no-fund --loglevel=error)
  (cd frontend && npm run build)
fi
cd backend
../.venv/bin/python -m app.cli demo
echo; echo "→ Abre http://localhost:$PORT   (demo@gcintelligence.local / demo1234)"
echo "  Los correos de alerta se guardan en demo/outbox/. Ctrl+C para salir."
exec ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
