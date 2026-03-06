#!/bin/bash
set -euo pipefail

API_BASE=${CORE_API_URL:-http://localhost:8000}
API="$API_BASE/api/v1"
KEY=${API_KEY_ADMIN:?API_KEY_ADMIN is required}
LEAD_ID=""
POST_ID=""

cleanup() {
  if [ -n "${POST_ID}" ]; then
    curl -sf -X DELETE "$API/scheduled-posts/$POST_ID" \
      -H "X-API-Key: $KEY" >/dev/null || true
  fi

  if [ -n "${LEAD_ID}" ]; then
    curl -sf -X DELETE "$API/leads/$LEAD_ID" \
      -H "X-API-Key: $KEY" >/dev/null || true
  fi
}
trap cleanup EXIT

LEAD_ID=$(curl -sf -X POST "$API/leads" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"source":"telegram_bot","name":"Integration Lead"}' | jq -r '.id')

echo "✅ Lead created: $LEAD_ID"

curl -sf -X POST "$API/events" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"lead_id\":\"$LEAD_ID\",\"type\":\"bot_start\",\"payload\":{}}" >/dev/null

echo "✅ Event created"

POST_ID=$(curl -sf -X POST "$API/scheduled-posts" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Integration test post","publish_at":"2099-01-01T00:00:00Z","status":"draft"}' | jq -r '.id')

echo "✅ Scheduled post created: $POST_ID"

JOB_COUNT=$(curl -sf -X GET "$API/contract-jobs?status=new&count_only=true" \
  -H "X-API-Key: $KEY" | jq -r '.count // 0')

echo "✅ Contract jobs endpoint available (new count: $JOB_COUNT)"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API/admin/api-keys" \
  -H "X-API-Key: ${API_KEY_BOT:-invalid}" || true)
if [ "$HTTP_CODE" = "403" ] || [ "$HTTP_CODE" = "401" ]; then
  echo "✅ Scope enforcement works"
else
  echo "❌ Scope enforcement FAILED"
  exit 1
fi

echo "🎉 Integration test passed"
