#!/bin/bash
set -euo pipefail

API_BASE=${CORE_API_URL:-http://localhost:8000}
API="$API_BASE/api/v1"
KEY=${API_KEY_ADMIN:?API_KEY_ADMIN is required}

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

JOB_ID=$(curl -sf -X POST "$API/contract-jobs" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"input_mode":"text_only","document_text":"Test contract text"}' | jq -r '.id')

echo "✅ Contract job created: $JOB_ID"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API/admin/api-keys" \
  -H "X-API-Key: ${API_KEY_BOT:-invalid}" || true)
if [ "$HTTP_CODE" = "403" ] || [ "$HTTP_CODE" = "401" ]; then
  echo "✅ Scope enforcement works"
else
  echo "❌ Scope enforcement FAILED"
  exit 1
fi

echo "🎉 Integration test passed"
