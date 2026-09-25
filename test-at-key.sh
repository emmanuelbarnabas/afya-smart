#!/usr/bin/env bash
# Pima Africa's Talking API key + username (haitumii salio — bure kabisa).
#   ./test-at-key.sh <username> [api_key]
# Kama api_key haijatolewa, inatumia ile iliyo kwenye backend/.env
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
USERNAME="${1:?Matumizi: ./test-at-key.sh <username> [api_key]}"
KEY="${2:-$(grep '^AT_API_KEY=' "$ROOT/backend/.env" | cut -d= -f2-)}"

cd "$ROOT/backend"
.venv/bin/python - "$USERNAME" "$KEY" <<'PY'
import sys
import africastalking

username, key = sys.argv[1], sys.argv[2]
africastalking.initialize(username, key)
try:
    data = africastalking.Application.fetch_application_data()
    print(f"✅ VALID — username='{username}' → {data}")
except Exception as e:
    print(f"❌ IMEKATALIWA — username='{username}' → {e}")
PY
