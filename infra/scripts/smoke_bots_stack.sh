#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

COMPOSE_FILE="${SMOKE_COMPOSE_FILE:-infra/compose/docker-compose.prod.yml}"
CORE_API_URL="${CORE_API_URL:-http://localhost:${CORE_API_PUBLISH_PORT:-8000}}"
API_KEY_ADMIN="${API_KEY_ADMIN:-}"
SMOKE_BUILD="${SMOKE_BUILD:-1}"
SMOKE_SKIP_UP="${SMOKE_SKIP_UP:-0}"
SMOKE_RUN_E2E="${SMOKE_RUN_E2E:-1}"
SMOKE_HEALTH_TIMEOUT_SECONDS="${SMOKE_HEALTH_TIMEOUT_SECONDS:-180}"
SMOKE_LOG_SINCE="${SMOKE_LOG_SINCE:-10m}"
SMOKE_REQUIRED_WORKERS="${SMOKE_REQUIRED_WORKERS:-news-generate,news-telegram-ingest,news-publish,news-reader-digest}"
SMOKE_SERVICES="${SMOKE_SERVICES:-postgres,core-api,lead-bot,news-admin-bot,news-reader-bot,news-reader-digest,news-generate,news-telegram-ingest,news-publish}"

if [ -z "$API_KEY_ADMIN" ]; then
  echo "ERROR: API_KEY_ADMIN is required (set in .env or environment)"
  exit 1
fi

lead_poll_token="${LEAD_BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
news_admin_poll_token="${NEWS_ADMIN_BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
reader_poll_token="${READER_BOT_TOKEN:-}"

if [ -z "${lead_poll_token}" ]; then
  echo "ERROR: LEAD_BOT_TOKEN or TELEGRAM_BOT_TOKEN must be set for lead-bot"
  exit 1
fi

if [ -z "${news_admin_poll_token}" ]; then
  echo "ERROR: NEWS_ADMIN_BOT_TOKEN or TELEGRAM_BOT_TOKEN must be set for news-admin-bot"
  exit 1
fi

if [ -z "${reader_poll_token}" ]; then
  echo "ERROR: READER_BOT_TOKEN must be set for news-reader-bot"
  exit 1
fi

if [ "${lead_poll_token}" = "${news_admin_poll_token}" ]; then
  echo "ERROR: lead-bot and news-admin-bot use the same polling token. Set separate LEAD_BOT_TOKEN and NEWS_ADMIN_BOT_TOKEN."
  exit 1
fi

if [ "${lead_poll_token}" = "${reader_poll_token}" ]; then
  echo "ERROR: lead-bot and news-reader-bot use the same polling token. Set separate LEAD_BOT_TOKEN and READER_BOT_TOKEN."
  exit 1
fi

if [ "${news_admin_poll_token}" = "${reader_poll_token}" ]; then
  echo "ERROR: news-admin-bot and news-reader-bot use the same polling token. Set separate NEWS_ADMIN_BOT_TOKEN and READER_BOT_TOKEN."
  exit 1
fi

readarray -t SERVICES < <(printf '%s' "$SMOKE_SERVICES" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | awk 'NF>0')
if [ "${#SERVICES[@]}" -eq 0 ]; then
  echo "ERROR: SMOKE_SERVICES resolved to empty list"
  exit 1
fi

echo "[1/9] Compose file: ${COMPOSE_FILE}"
echo "Services: ${SERVICES[*]}"

if [ "${SMOKE_SKIP_UP}" != "1" ]; then
  echo "[2/9] Starting services..."
  if [ "${SMOKE_BUILD}" = "1" ]; then
    docker compose -f "${COMPOSE_FILE}" up -d --build "${SERVICES[@]}"
  else
    docker compose -f "${COMPOSE_FILE}" up -d "${SERVICES[@]}"
  fi
else
  echo "[2/9] Skipping compose up (SMOKE_SKIP_UP=1)"
fi

echo "[3/9] Waiting for core-api health (${CORE_API_URL}/health)..."
deadline=$((SECONDS + SMOKE_HEALTH_TIMEOUT_SECONDS))
until curl -fsS "${CORE_API_URL}/health" >/dev/null 2>&1; do
  if [ "${SECONDS}" -ge "${deadline}" ]; then
    echo "ERROR: core-api health check timeout"
    exit 1
  fi
  sleep 2
done
echo "OK: core-api health is up"

echo "[4/9] Checking required services are running..."
running_services="$(docker compose -f "${COMPOSE_FILE}" ps --status running --services)"
for svc in "${SERVICES[@]}"; do
  if ! printf '%s\n' "${running_services}" | grep -Fx "${svc}" >/dev/null; then
    echo "ERROR: service not running: ${svc}"
    docker compose -f "${COMPOSE_FILE}" ps
    exit 1
  fi
done
echo "OK: all required services are running"

echo "[5/9] Checking workers/status..."
workers_json="$(curl -fsS -H "X-API-Key: ${API_KEY_ADMIN}" "${CORE_API_URL}/api/v1/workers/status")"
IFS=',' read -r -a required_workers <<<"${SMOKE_REQUIRED_WORKERS}"
for worker in "${required_workers[@]}"; do
  trimmed="$(echo "${worker}" | xargs)"
  [ -n "${trimmed}" ] || continue
  active_count="$(echo "${workers_json}" | jq -r --arg W "${trimmed}" '[.workers[] | select(.worker_id == $W and .active == true)] | length')"
  if [ "${active_count}" -eq 0 ]; then
    echo "ERROR: worker is not active: ${trimmed}"
    echo "${workers_json}" | jq .
    exit 1
  fi
done
echo "OK: required workers are active"

echo "[6/9] Running API integration smoke..."
bash infra/scripts/integration_test.sh

echo "[7/9] Running reader-digest smoke..."
bash infra/scripts/smoke_reader_digest.sh

if [ "${SMOKE_RUN_E2E}" = "1" ]; then
  echo "[8/9] Running reader->lead E2E smoke..."
  bash infra/scripts/e2e_reader_to_lead.sh
else
  echo "[8/9] Skipping E2E (SMOKE_RUN_E2E=0)"
fi

echo "[9/9] Checking recent logs for critical startup/runtime issues..."
declare -a LOG_SERVICES=("lead-bot" "news-admin-bot" "news-reader-bot" "news-generate" "news-telegram-ingest" "news-publish" "news-reader-digest")
for svc in "${LOG_SERVICES[@]}"; do
  logs="$(docker compose -f "${COMPOSE_FILE}" logs --since "${SMOKE_LOG_SINCE}" --tail=300 "${svc}" || true)"
  if echo "${logs}" | grep -Eqi "NameResolutionError|Connection refused|Failed to establish a new connection|401 Client Error|Unauthorized|Conflict: terminated by other getUpdates request|Network is unreachable"; then
    echo "ERROR: critical log pattern found in ${svc} (last ${SMOKE_LOG_SINCE})"
    echo "----- ${svc} logs tail -----"
    echo "${logs}" | tail -n 120
    exit 1
  fi
done
echo "OK: no critical log patterns detected"

echo "🎉 Bots stack smoke PASSED"
