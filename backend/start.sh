#!/usr/bin/env bash
#ENTRYPOINT ya container ya Afya Smart (FastAPI).
# 1. Alembic migrations  2. safety-net create_all  3. seed demo (ikiwa ni empty)
# 4. uvicorn kwenye 0.0.0.0:8000
set -e

echo "[start] Migrations (alembic upgrade head)..."
python -m alembic upgrade head

echo "[start] Safety net: create any table migrations have not caught yet..."
python - <<'PY'
from app.core.database import Base, engine
import app.models  # register all tables on Base.metadata
Base.metadata.create_all(bind=engine)
PY

# Seed ni idempotent (ensure_* + history inarudi ikiwa ipo tayari). Isipofanikiwe,
# API bado inafanya kazi — maombi yanategemea rules engine pale model haipo.
echo "[start] Demo data (ikiwa ni empty)..."
python -m app.seed || echo "[start] Seed imekoseka (si mbaya — kuendelea)"

echo "[start] Uvicorn :8000 (ENVIRONMENT=${ENVIRONMENT:-unset})"
# SQLite inaserialize writes → workers 1. Ukitumia PostgreSQL unaweza kuongeza.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
