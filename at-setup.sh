#!/usr/bin/env bash
# Kuunganisha Africa's Talking credentials na Afya Smart.
#   ./at-setup.sh   → inakuuliza username na API key, inaziweka kwenye backend/.env
#                     na kuwasha upya backend.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/backend/.env"

echo "=== Africa's Talking Setup ==="
echo "Pata credentials: https://account.africastalking.com → Settings → API Keys"
echo ""

read -rp "AT_USERNAME (sandbox au username yako): " AT_USER
read -rsp "AT_API_KEY: " AT_KEY
echo ""
read -rp "AT_PHONE_NUMBER (sender ID, Enter ku-ruka): " AT_PHONE

# Ondoa mistari ya zamani ya AT kisha weka mpya
sed -i '/^AT_USERNAME=/d; /^AT_API_KEY=/d; /^AT_PHONE_NUMBER=/d' "$ENV_FILE"
{
  echo "AT_USERNAME=$AT_USER"
  echo "AT_API_KEY=$AT_KEY"
  echo "AT_PHONE_NUMBER=$AT_PHONE"
} >> "$ENV_FILE"

echo ""
echo "✅ Credentials zimewekwa kwenye $ENV_FILE"
echo "Inawasha upya backend..."

pkill -f "uvicorn app.main" 2>/dev/null || true
sleep 1
cd "$ROOT/backend"
setsid nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/afya_api.log 2>&1 < /dev/null &
sleep 3

CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health)
if [ "$CODE" = "200" ]; then
  echo "✅ Backend imeanza upya na credentials mpya (health: 200)"
  echo ""
  echo "Hatua iliyofuata kwenye dashi ya AT:"
  echo "  1. USSD → Create channel → Callback URL:"
  echo "     $(cat /tmp/afya_tunnel.log 2>/dev/null | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)/api/v1/ussd"
  echo "  2. Kwenye simu piga: *384*<channelID>#"
else
  echo "❌ Backend haikupatikana — angalia: tail -20 /tmp/afya_api.log"
fi
