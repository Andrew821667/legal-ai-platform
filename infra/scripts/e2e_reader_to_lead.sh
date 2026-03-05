#!/bin/bash
set -euo pipefail

API_BASE="${CORE_API_URL:-http://localhost:8000}"
API="${API_BASE%/}/api/v1"
API_KEY_ADMIN="${API_KEY_ADMIN:?API_KEY_ADMIN is required}"
E2E_TEST_USER_ID="${E2E_TEST_USER_ID:-321681061}"

POST_ID=""
LEAD_ID=""

cleanup() {
  if [ -n "${LEAD_ID}" ]; then
    curl -fsS -X DELETE "${API}/leads/${LEAD_ID}" \
      -H "X-API-Key: ${API_KEY_ADMIN}" >/dev/null || true
  fi
  if [ -n "${POST_ID}" ]; then
    curl -fsS -X DELETE "${API}/scheduled-posts/${POST_ID}" \
      -H "X-API-Key: ${API_KEY_ADMIN}" >/dev/null || true
  fi
}
trap cleanup EXIT

api_get() {
  local path="$1"
  curl -fsS -H "X-API-Key: ${API_KEY_ADMIN}" "${API}${path}"
}

api_post() {
  local path="$1"
  local payload="$2"
  curl -fsS -X POST "${API}${path}" \
    -H "X-API-Key: ${API_KEY_ADMIN}" \
    -H "Content-Type: application/json" \
    -d "${payload}"
}

echo "[1/7] Проверяю активность ключевых воркеров..."
WORKERS_JSON="$(api_get "/workers/status")"
for worker in news-generate news-telegram-ingest news-publish news-reader-digest; do
  active_count="$(echo "${WORKERS_JSON}" | jq -r --arg W "${worker}" '[.workers[] | select(.worker_id == $W and .active == true)] | length')"
  if [ "${active_count}" -eq 0 ]; then
    echo "ERROR: воркер ${worker} неактивен"
    exit 1
  fi
done
echo "OK: воркеры активны"

echo "[2/7] Создаю тестовый posted-пост..."
PUBLISH_AT="$(
python3 - <<'PY'
from datetime import datetime, timezone, timedelta
print((datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat())
PY
)"
POST_PAYLOAD="$(jq -cn \
  --arg title "E2E Reader Flow Post" \
  --arg text "E2E Reader Flow test content" \
  --arg source_url "https://example.com/e2e-reader-flow" \
  --arg publish_at "${PUBLISH_AT}" \
  '{
      title: $title,
      text: $text,
      source_url: $source_url,
      publish_at: $publish_at,
      status: "posted",
      format_type: "standard",
      cta_type: "soft"
    }'
)"
POST_ID="$(api_post "/scheduled-posts" "${POST_PAYLOAD}" | jq -r '.id')"
if [ -z "${POST_ID}" ] || [ "${POST_ID}" = "null" ]; then
  echo "ERROR: не удалось создать тестовый post"
  exit 1
fi
echo "OK: post_id=${POST_ID}"

echo "[3/7] Отправляю reader feedback-сигналы..."
api_post "/scheduled-posts/${POST_ID}/feedback" "$(jq -cn \
  --argjson uid "${E2E_TEST_USER_ID}" \
  '{source:"comment",signal_key:"reader.weekly.opened",signal_value:1,actor_name:"reader_bot",telegram_user_id:$uid}')" >/dev/null
api_post "/scheduled-posts/${POST_ID}/feedback" "$(jq -cn \
  --argjson uid "${E2E_TEST_USER_ID}" \
  '{source:"comment",signal_key:"reader.idea.requested",signal_value:1,actor_name:"reader_bot",telegram_user_id:$uid}')" >/dev/null
api_post "/scheduled-posts/${POST_ID}/feedback" "$(jq -cn \
  --argjson uid "${E2E_TEST_USER_ID}" \
  '{source:"comment",signal_key:"reader.consultation.intent",signal_value:1,actor_name:"reader_bot",telegram_user_id:$uid}')" >/dev/null
echo "OK: reader feedback записан"

echo "[4/7] Проверяю агрегаты reader-summary..."
SUMMARY_JSON="$(api_get "/scheduled-posts/feedback/reader-summary?days=7")"
consult_summary="$(echo "${SUMMARY_JSON}" | jq -r '.stats.consultation_intent // 0')"
if [ "${consult_summary}" -lt 1 ]; then
  echo "ERROR: consultation_intent не отразился в summary"
  exit 1
fi
echo "OK: consultation_intent=${consult_summary}"

echo "[5/7] Создаю reader-referral lead..."
LEAD_PAYLOAD="$(jq -cn \
  --argjson uid "${E2E_TEST_USER_ID}" \
  --arg name "E2E Reader Lead" \
  --arg email "e2e-reader@example.com" \
  --arg notes "[READER_REFERRAL]\npost_id=${POST_ID}" \
  '{
      source:"telegram_bot",
      telegram_user_id:$uid,
      name:$name,
      email:$email,
      cta_variant:"reader_referral",
      status:"qualified",
      notes:$notes
    }'
)"
LEAD_ID="$(api_post "/leads" "${LEAD_PAYLOAD}" | jq -r '.id')"
if [ -z "${LEAD_ID}" ] || [ "${LEAD_ID}" = "null" ]; then
  echo "ERROR: не удалось создать lead"
  exit 1
fi
echo "OK: lead_id=${LEAD_ID}"

echo "[6/7] Проверяю воронку reader-funnel..."
FUNNEL_JSON="$(api_get "/scheduled-posts/feedback/reader-funnel?days=7")"
consult_users_to_lead="$(echo "${FUNNEL_JSON}" | jq -r '.conversion.consultation_users_to_reader_lead // 0')"
reader_referral_created="$(echo "${FUNNEL_JSON}" | jq -r '.leads.reader_referral_created // 0')"
if [ "${consult_users_to_lead}" -lt 1 ] || [ "${reader_referral_created}" -lt 1 ]; then
  echo "ERROR: reader-funnel не показывает ожидаемую конверсию"
  echo "${FUNNEL_JSON}" | jq .
  exit 1
fi
echo "OK: consultation_users_to_reader_lead=${consult_users_to_lead}, reader_referral_created=${reader_referral_created}"

echo "[7/7] Проверяю endpoint активности reader-digest..."
api_get "/workers/news-reader-digest/activity?hours=24&limit=10" >/dev/null
echo "OK: worker activity endpoint доступен"

echo "🎉 E2E reader->lead smoke passed"
