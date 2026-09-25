#!/usr/bin/env bash
# Afya Smart — washza wa dev wa haraka.
# Matumizi:
#   ./dev.sh          # anza DB + backend + dashboard (nyuma), kisha fungua browser
#   ./dev.sh stop     # zima zote
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

start() {
  echo "==> 1/3 PostgreSQL (docker)"
  docker compose -f "$ROOT/infra/docker-compose.yml" up -d

  echo "==> 2/3 Backend (FastAPI :8000)"
  (cd "$ROOT/backend" && [ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements.txt; }
   [ -f afyasmart.db ] || .venv/bin/python -m app.seed || true
   setsid nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/afya_api.log 2>&1 < /dev/null &
  )

  echo "==> 3/3 Dashboard (Vite :5173)"
  (cd "$ROOT/dashboard" && [ -d node_modules ] || npm install
   setsid nohup npm run dev > /tmp/afya_dash.log 2>&1 < /dev/null &
  )

  sleep 4
  echo ""
  echo "✅ Imeanza:"
  echo "   Dashibodi : http://localhost:5173   (fungua kwenye browser)"
  echo "   API docs  : http://localhost:8000/docs"
  echo "   Logs      : tail -f /tmp/afya_api.log /tmp/afya_dash.log"
}

stop() {
  pkill -f "uvicorn app.main" 2>/dev/null || true
  pkill -f vite 2>/dev/null || true
  echo "Zimazwa."
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  *) echo "Matumizi: ./dev.sh [start|stop]" ;;
esac
