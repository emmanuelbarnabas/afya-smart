#!/usr/bin/env bash
# Anzisha mfumo wote wa Afya Smart kwa amri moja:
#   1. Backend ya platform (FastAPI, :8000)  — inaunganishwa na Africa's Talking
#   2. Tunnel ya umma (cloudflared)          — URL ya kudumu kwa siku ya leo
#   3. Prototype ya root (Flask, :5000)       — dashboard + USSD demo + fairness
#
#   ./start-all.sh      # anzisha kilichokosekana (kila kipande ni salama kurudiwia)
#
# Kila kipande kinaendeshwa nyuma (background). Ukishamaliza, fungua dashboard
# kwenye PC na piga *384*<channel># kwenye simu ya sandbox ya Africa's Talking.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

wait_url() {  # wait_url <url> <seconds>
  for i in $(seq 1 "${2:-15}"); do
    code=$(curl -s -o /dev/null -w "%{http_code}" -m 2 "$1" 2>/dev/null || true)
    [ "$code" = "200" ] && return 0
    sleep 1
  done
  return 1
}

# 1) Backend (FastAPI :8000) -----------------------------------------------
if curl -s -o /dev/null -m 2 http://127.0.0.1:8000/api/v1/health; then
  echo "✅ Backend (:8000) tayari inaendeshwa"
else
  echo "Inaanzisha backend (:8000)..."
  (cd backend && setsid nohup .venv/bin/uvicorn app.main:app --port 8000 \
    > /tmp/afya_api.log 2>&1 < /dev/null &)
  wait_url http://127.0.0.1:8000/api/v1/health 20 \
    && echo "✅ Backend imeanza (:8000)" \
    || { echo "❌ Backend haikuanzia — tail -20 /tmp/afya_api.log"; exit 1; }
fi

# 2) Tunnel ya umma (cloudflared → :8000) ----------------------------------
URL=$(grep -hoE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/afya_tunnel.log 2>/dev/null | head -1 || true)
if pgrep -f "cloudflared tunnel" > /dev/null && [ -n "$URL" ]; then
  echo "✅ Tunnel tayari inaendeshwa: $URL"
else
  echo "Inaanzisha tunnel ya umma..."
  [ -x ./bin/cloudflared ] || { echo "❌ bin/cloudflared haipo — ./tunnel.sh itaipakua"; exit 1; }
  pkill -f "cloudflared tunnel" 2>/dev/null || true
  sleep 1
  setsid nohup ./bin/cloudflared tunnel --url http://localhost:8000 \
    > /tmp/afya_tunnel.log 2>&1 < /dev/null &
  URL=""
  for i in $(seq 1 25); do
    sleep 1
    URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/afya_tunnel.log | head -1)
    [ -n "$URL" ] && break
  done
  [ -n "$URL" ] && echo "✅ Tunnel imeanza: $URL" \
    || { echo "❌ Tunnel haikuanzia — tail -20 /tmp/afya_tunnel.log"; exit 1; }
fi

# 3) Prototype ya root (Flask :5000) ---------------------------------------
if curl -s -o /dev/null -m 2 http://127.0.0.1:5000/health; then
  echo "✅ Prototype (:5000) tayari inaendeshwa"
else
  echo "Inaanzisha prototype (:5000)..."
  setsid nohup .venv/bin/python app.py > /tmp/afya_web.log 2>&1 < /dev/null &
  wait_url http://127.0.0.1:5000/health 20 \
    && echo "✅ Prototype imeanza (:5000)" \
    || { echo "❌ Prototype haikuanzia — tail -20 /tmp/afya_web.log"; exit 1; }
fi

cat <<EOF

================================================================
🎉 MFUMO WOTE UKO HAI
----------------------------------------------------------------
📞 SIMU HALISI (Africa's Talking)
   Weka hii kwenye Callback URL ya channel yako kwenye
   https://account.africastalking.com → USSD:
       $URL/api/v1/ussd
   Kisha piga kwenye simu ya sandbox:  *384*<channelID>#

💻 DASHBOARD KWENYE PC (fungua kwenye browser)
   Platform kamili :  http://127.0.0.1:8000/dashboard
   Prototype        :  http://127.0.0.1:5000/dashboard
   Ripoti ya haki   :  http://127.0.0.1:5000/fairness
   USSD simulator   :  http://127.0.0.1:5000/ussd-demo  (maswali mapya)
                       http://127.0.0.1:8000/ussd-demo  (kama AT halisi)
📱 SIMU ZA NJE (kutoka network yoyote)
                       $URL/ussd-demo
                       $URL/dashboard

   Kumbuka: URL ya tunnel (trycloudflare) hubadilika pale script
   inapoanzisha tunnel mpya — kisha badilisha callback kwenye dashi
   ya AT. Logs: tail -f /tmp/afya_api.log /tmp/afya_tunnel.log
================================================================
EOF
