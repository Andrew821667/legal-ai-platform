#!/bin/bash
set -euo pipefail

API_BASE=${CORE_API_URL:-http://localhost:8000}
ALERT_BOT_TOKEN=${ALERT_BOT_TOKEN:-}
ALERT_CHAT_ID=${ALERT_CHAT_ID:-}

if ! curl -sf -H "X-API-Key: ${API_KEY_ADMIN:?API_KEY_ADMIN is required}" "$API_BASE/health/detailed" >/dev/null; then
  if [ -n "$ALERT_BOT_TOKEN" ] && [ -n "$ALERT_CHAT_ID" ]; then
    curl -s "https://api.telegram.org/bot$ALERT_BOT_TOKEN/sendMessage" \
      -d "chat_id=$ALERT_CHAT_ID" \
      -d "text=🔴 Legal AI Platform: health check failed!" >/dev/null
  fi
  exit 1
fi

PENDING=$(curl -sf -H "X-API-Key: $API_KEY_ADMIN" \
  "$API_BASE/api/v1/contract-jobs?status=new&count_only=true" | jq -r '.count // 0')
ANY_ACTIVE=$(curl -sf -H "X-API-Key: $API_KEY_ADMIN" \
  "$API_BASE/api/v1/workers/status" | jq -r '.any_active // false')

if [ "$PENDING" -gt 0 ] && [ "$ANY_ACTIVE" = "false" ] && [ -n "$ALERT_BOT_TOKEN" ] && [ -n "$ALERT_CHAT_ID" ]; then
  curl -s "https://api.telegram.org/bot$ALERT_BOT_TOKEN/sendMessage" \
    -d "chat_id=$ALERT_CHAT_ID" \
    -d "text=⚠️ ${PENDING} контрактов ждут анализа, но воркер не отвечает!" >/dev/null
fi
