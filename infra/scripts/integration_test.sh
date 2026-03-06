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

SUMMARY_TOTAL=$(curl -sf -X GET "$API/contract-jobs/summary" \
  -H "X-API-Key: $KEY" | jq -r '.total // -1')
if [ "$SUMMARY_TOTAL" -ge 0 ]; then
  echo "✅ Contract jobs summary available (total: $SUMMARY_TOTAL)"
else
  echo "❌ Contract jobs summary FAILED"
  exit 1
fi

OPS_OVERVIEW_OK=$(curl -sf -X GET "$API/contract-jobs/ops-overview?window_hours=24&stale_minutes=30&sample_limit=5&events_limit=10" \
  -H "X-API-Key: $KEY" | jq -r 'if .summary.total >= 0 then "ok" else "fail" end')
if [ "$OPS_OVERVIEW_OK" = "ok" ]; then
  echo "✅ Contract jobs ops-overview available"
else
  echo "❌ Contract jobs ops-overview FAILED"
  exit 1
fi

MAINTENANCE_DRY=$(curl -sf -X POST "$API/contract-jobs/maintenance?dry_run=true&retry_failed=true&limit_each=20&stale_minutes=30" \
  -H "X-API-Key: $KEY" | jq -r '.dry_run // false')
if [ "$MAINTENANCE_DRY" = "true" ]; then
  echo "✅ Contract jobs maintenance dry-run works"
else
  echo "❌ Contract jobs maintenance dry-run FAILED"
  exit 1
fi

RETRY_DRY=$(curl -sf -X POST "$API/contract-jobs/retry-failed?dry_run=true&limit=10" \
  -H "X-API-Key: $KEY" | jq -r '.dry_run // false')
if [ "$RETRY_DRY" = "true" ]; then
  echo "✅ Contract jobs retry-failed dry-run works"
else
  echo "❌ Contract jobs retry-failed dry-run FAILED"
  exit 1
fi

FINALIZE_DRY=$(curl -sf -X POST "$API/contract-jobs/finalize-exhausted-new?dry_run=true&limit=10" \
  -H "X-API-Key: $KEY" | jq -r '.dry_run // false')
if [ "$FINALIZE_DRY" = "true" ]; then
  echo "✅ Contract jobs finalize-exhausted-new dry-run works"
else
  echo "❌ Contract jobs finalize-exhausted-new dry-run FAILED"
  exit 1
fi

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API/admin/api-keys" \
  -H "X-API-Key: ${API_KEY_BOT:-invalid}" || true)
if [ "$HTTP_CODE" = "403" ] || [ "$HTTP_CODE" = "401" ]; then
  echo "✅ Scope enforcement works"
else
  echo "❌ Scope enforcement FAILED"
  exit 1
fi

echo "🎉 Integration test passed"
