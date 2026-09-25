#!/usr/bin/env bash
# Anzisha tunnel ya umma (cloudflared) → backend ya Afya Smart (:8000).
# Inatumika kwa callback ya Africa's Talking na kupima kutoka simu.
#   ./tunnel.sh          # anza na onyesha URL ya umma
#   ./tunnel.sh stop     # zima tunnel
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

start() {
  pkill -f "cloudflared tunnel" 2>/dev/null || true
  sleep 1
  cd "$ROOT"
  setsid nohup ./bin/cloudflared tunnel --url http://localhost:8000 \
    > /tmp/afya_tunnel.log 2>&1 < /dev/null &
  echo "Inasubiri URL ya umma..."
  for i in $(seq 1 20); do
    sleep 1
    URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/afya_tunnel.log | head -1)
    [ -n "$URL" ] && break
  done
  if [ -n "$URL" ]; then
    echo ""
    echo "✅ Tunnel ipo: $URL"
    echo "   USSD Demo (simu): $URL/ussd-demo"
    echo "   AT Callback     : $URL/api/v1/ussd"
    echo "   Logs            : tail -f /tmp/afya_tunnel.log"
  else
    echo "❌ Haikupata URL — angalia: tail -20 /tmp/afya_tunnel.log"
  fi
}

stop() {
  pkill -f "cloudflared tunnel" 2>/dev/null || true
  echo "Tunnel imezimwa."
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  *) echo "Matumizi: ./tunnel.sh [start|stop]" ;;
esac
