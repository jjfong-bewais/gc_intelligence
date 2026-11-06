.PHONY: setup demo test dev-api dev-web build ingest
setup:      ; ./scripts/setup.sh
demo:       ; ./scripts/demo.sh
test:       ; cd backend && ../.venv/bin/python -m pytest
build:      ; cd frontend && npm run build
dev-api:    ; cd backend && GC_MODE=demo MAIL_PROVIDER=file ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000
dev-web:    ; cd frontend && npm run dev
ingest:     ; cd backend && ../.venv/bin/python -m app.cli ingest
