#!/usr/bin/env bash
# Prepara todo DENTRO del repo: .venv (Python) y, si no hay Node, .node (vía nodeenv).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3,10))' 2>/dev/null; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "Se necesita Python >= 3.10"; exit 1; }

if [ ! -x .venv/bin/python ]; then echo "→ creando .venv con $PY"; "$PY" -m venv .venv; fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r backend/requirements-dev.txt
echo "✓ dependencias de Python"

if [ "${SKIP_FRONTEND:-0}" != "1" ]; then
  if ! command -v node >/dev/null || ! node -e 'process.exit(+process.versions.node.split(".")[0] < 18)'; then
    echo "→ Node >= 18 no encontrado: instalando uno local en .node (nodeenv)"
    .venv/bin/python -m pip install -q nodeenv
    [ -d .node ] || .venv/bin/nodeenv -q --node=22.11.0 .node
    export PATH="$PWD/.node/bin:$PATH"
  fi
  (cd frontend && npm install --no-audit --no-fund --loglevel=error)
  echo "✓ dependencias del frontend"
fi
