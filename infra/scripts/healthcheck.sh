#!/bin/bash
set -euo pipefail

API_BASE="${CORE_API_URL:-http://localhost:8000}"
API_KEY_ADMIN="${API_KEY_ADMIN:?API_KEY_ADMIN is required}"
ALERT_BOT_TOKEN="${ALERT_BOT_TOKEN:-}"
ALERT_CHAT_ID="${ALERT_CHAT_ID:-}"
ALERT_STATE_FILE="${ALERT_STATE_FILE:-/tmp/legal-ai-alert-state.json}"
ALERT_COOLDOWN_SECONDS="${ALERT_COOLDOWN_SECONDS:-1800}"
SLA_ALERTS_ENABLED="${SLA_ALERTS_ENABLED:-1}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DOCKER_BIN="${DOCKER_BIN:-$(command -v docker || true)}"
COMPOSE_BIN="${COMPOSE_BIN:-$(command -v docker-compose || true)}"
if [ -z "${DOCKER_BIN}" ] && [ -x "/usr/local/bin/docker" ]; then
  DOCKER_BIN="/usr/local/bin/docker"
fi
if [ -z "${COMPOSE_BIN}" ] && [ -x "/opt/homebrew/bin/docker-compose" ]; then
  COMPOSE_BIN="/opt/homebrew/bin/docker-compose"
fi
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-compose}"
COMPOSE_FILE="${COMPOSE_FILE:-${PROJECT_DIR}/infra/compose/docker-compose.prod.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-${PROJECT_DIR}/.env}"
REQUIRED_NEWS_WORKERS="${REQUIRED_NEWS_WORKERS:-news-generate,news-telegram-ingest,news-publish,news-reader-digest}"
DRAFT_MAX_IDLE_HOURS="${DRAFT_MAX_IDLE_HOURS:-24}"
DUE_POSTS_ALERT_THRESHOLD="${DUE_POSTS_ALERT_THRESHOLD:-0}"
CONTRACT_EXHAUSTED_NEW_ALERT_THRESHOLD="${CONTRACT_EXHAUSTED_NEW_ALERT_THRESHOLD:-0}"
CONTRACT_STALE_PROCESSING_ALERT_THRESHOLD="${CONTRACT_STALE_PROCESSING_ALERT_THRESHOLD:-0}"
CONTRACT_FAILED_RETRYABLE_ALERT_THRESHOLD="${CONTRACT_FAILED_RETRYABLE_ALERT_THRESHOLD:-0}"
TELEGRAM_RECOVERY_ENABLED="${TELEGRAM_RECOVERY_ENABLED:-0}"
TELEGRAM_TLS_CHECK_CONTAINER="${TELEGRAM_TLS_CHECK_CONTAINER:-legal-ai-lead-bot}"
TELEGRAM_TLS_CHECK_HOST="${TELEGRAM_TLS_CHECK_HOST:-api.telegram.org}"
TELEGRAM_TLS_CHECK_TIMEOUT_SECONDS="${TELEGRAM_TLS_CHECK_TIMEOUT_SECONDS:-8}"
TELEGRAM_RECOVERY_COOLDOWN_SECONDS="${TELEGRAM_RECOVERY_COOLDOWN_SECONDS:-300}"
TELEGRAM_RECOVERY_SERVICES="${TELEGRAM_RECOVERY_SERVICES:-lead-bot news-admin-bot news-reader-bot news-publish news-reader-digest}"
TELEGRAM_RECOVERY_STOP_HAPP_TUNNEL="${TELEGRAM_RECOVERY_STOP_HAPP_TUNNEL:-0}"
TELEGRAM_RECOVERY_STOP_HAPP_APP="${TELEGRAM_RECOVERY_STOP_HAPP_APP:-0}"
TELEGRAM_RECOVERY_RESTART_SERVICES="${TELEGRAM_RECOVERY_RESTART_SERVICES:-1}"
TELEGRAM_RECOVERY_TUN_INTERFACES="${TELEGRAM_RECOVERY_TUN_INTERFACES:-utun}"

api_get() {
  local url="$1"
  curl -fsS -H "X-API-Key: ${API_KEY_ADMIN}" "${url}"
}

_state_get_ts() {
  local key="$1"
  python3 - "$ALERT_STATE_FILE" "$key" <<'PY'
import json, os, sys
path, key = sys.argv[1], sys.argv[2]
if not os.path.exists(path):
    print(0)
    raise SystemExit(0)
try:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except Exception:
    print(0)
    raise SystemExit(0)
print(int((data or {}).get(key, 0) or 0))
PY
}

_state_set_ts() {
  local key="$1"
  local now_ts="$2"
  python3 - "$ALERT_STATE_FILE" "$key" "$now_ts" <<'PY'
import json, os, sys
path, key, now_ts = sys.argv[1], sys.argv[2], int(sys.argv[3])
data = {}
if os.path.exists(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh) or {}
    except Exception:
        data = {}
data[key] = now_ts
tmp_path = f"{path}.tmp"
with open(tmp_path, "w", encoding="utf-8") as fh:
    json.dump(data, fh)
os.replace(tmp_path, path)
PY
}

send_alert_once() {
  local key="$1"
  local text="$2"
  if [ -z "$ALERT_BOT_TOKEN" ] || [ -z "$ALERT_CHAT_ID" ]; then
    return 0
  fi
  local now_ts last_ts
  now_ts="$(date +%s)"
  last_ts="$(_state_get_ts "$key")"
  if [ $((now_ts - last_ts)) -lt "${ALERT_COOLDOWN_SECONDS}" ]; then
    return 0
  fi
  curl -fsS "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${ALERT_CHAT_ID}" \
    --data-urlencode "text=${text}" >/dev/null || return 0
  _state_set_ts "$key" "$now_ts"
}

docker_compose() {
  if [ -n "${COMPOSE_BIN}" ]; then
    "${COMPOSE_BIN}" -p "${COMPOSE_PROJECT_NAME}" --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
    return $?
  fi
  if [ -n "${DOCKER_BIN}" ]; then
    "${DOCKER_BIN}" compose -p "${COMPOSE_PROJECT_NAME}" --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
    return $?
  fi
  return 127
}

telegram_tls_check() {
  if [ -z "${DOCKER_BIN}" ]; then
    echo "docker_not_found"
    return 1
  fi
  "${DOCKER_BIN}" exec "${TELEGRAM_TLS_CHECK_CONTAINER}" python - \
    "${TELEGRAM_TLS_CHECK_HOST}" "${TELEGRAM_TLS_CHECK_TIMEOUT_SECONDS}" <<'PY'
import socket
import ssl
import sys

host = sys.argv[1]
timeout = float(sys.argv[2])
try:
    sock = socket.create_connection((host, 443), timeout=timeout)
    with ssl.create_default_context().wrap_socket(sock, server_hostname=host) as tls:
        print(f"tls_ok {host} {tls.version()}")
except Exception as exc:
    print(f"tls_failed {host} {type(exc).__name__}: {exc}")
    raise SystemExit(1)
PY
}

telegram_route_interface() {
  route get "${TELEGRAM_TLS_CHECK_HOST}" 2>/dev/null | awk '/interface:/{print $2; exit}'
}

telegram_route_is_tun() {
  local interface prefix
  interface="$(telegram_route_interface || true)"
  if [ -z "${interface}" ]; then
    return 1
  fi
  for prefix in ${TELEGRAM_RECOVERY_TUN_INTERFACES}; do
    case "${interface}" in
      "${prefix}"*) return 0 ;;
    esac
  done
  return 1
}

telegram_recovery_allowed() {
  local now_ts last_ts
  now_ts="$(date +%s)"
  last_ts="$(_state_get_ts "telegram_network_recovery")"
  if [ $((now_ts - last_ts)) -lt "${TELEGRAM_RECOVERY_COOLDOWN_SECONDS}" ]; then
    return 1
  fi
  _state_set_ts "telegram_network_recovery" "${now_ts}"
  return 0
}

restart_telegram_services() {
  if [ "${TELEGRAM_RECOVERY_RESTART_SERVICES}" != "1" ]; then
    return 0
  fi
  docker_compose restart ${TELEGRAM_RECOVERY_SERVICES}
}

recover_telegram_network() {
  if [ "${TELEGRAM_RECOVERY_ENABLED}" != "1" ]; then
    send_alert_once \
      "telegram_tls_failed" \
      "🔴 Telegram API недоступен из ${TELEGRAM_TLS_CHECK_CONTAINER}; recovery выключен."
    return 1
  fi
  if ! telegram_recovery_allowed; then
    echo "telegram_recovery_skipped_cooldown"
    return 1
  fi

  local route_interface
  route_interface="$(telegram_route_interface || true)"
  echo "telegram_recovery_started route_interface=${route_interface:-unknown}"

  if [ "${TELEGRAM_RECOVERY_STOP_HAPP_TUNNEL}" = "1" ] && telegram_route_is_tun; then
    pkill -f "/Applications/Happ Plus.app/Contents/PlugIns/Tunnel.appex" 2>/dev/null || true
    if [ "${TELEGRAM_RECOVERY_STOP_HAPP_APP}" = "1" ]; then
      pkill -f "/Applications/Happ Plus.app/Contents/MacOS/Happ" 2>/dev/null || true
    fi
    sleep 5
  fi

  if telegram_tls_check >/dev/null; then
    restart_telegram_services
    send_alert_once \
      "telegram_network_recovered" \
      "🟢 Telegram API восстановлен автоматически; перезапущены сервисы: ${TELEGRAM_RECOVERY_SERVICES}."
    return 0
  fi

  restart_telegram_services || true
  sleep 5
  if telegram_tls_check >/dev/null; then
    send_alert_once \
      "telegram_network_recovered_after_restart" \
      "🟢 Telegram API восстановлен после перезапуска сервисов: ${TELEGRAM_RECOVERY_SERVICES}."
    return 0
  fi

  send_alert_once \
    "telegram_network_recovery_failed" \
    "🔴 Telegram API всё ещё недоступен после automatic recovery. Проверьте VPN/TUN на Mac mini."
  return 1
}

# 1) Базовый health
if ! api_get "${API_BASE}/health/detailed" >/dev/null; then
  send_alert_once "health_detailed_failed" "🔴 AI Verdict Platform: health check failed!"
  exit 1
fi

# 1.1) Telegram API должен проходить полноценный TLS-handshake из контейнера.
if ! telegram_tls_check >/dev/null; then
  recover_telegram_network || true
fi

# 2) Контрактный backlog + отсутствие воркеров
CONTRACT_SUMMARY_JSON="$(api_get "${API_BASE}/api/v1/contract-jobs/summary")"
PENDING_RETRYABLE="$(echo "${CONTRACT_SUMMARY_JSON}" | jq -r '.new_retryable_count // .by_status.new // 0')"
PENDING_EXHAUSTED_NEW="$(echo "${CONTRACT_SUMMARY_JSON}" | jq -r '.new_exhausted_count // 0')"
PROCESSING_STALE_COUNT="$(echo "${CONTRACT_SUMMARY_JSON}" | jq -r '.processing_stale_count // 0')"
FAILED_RETRYABLE_COUNT="$(echo "${CONTRACT_SUMMARY_JSON}" | jq -r '.failed_retryable_count // 0')"
ANY_ACTIVE="$(api_get "${API_BASE}/api/v1/workers/status" | jq -r '.any_active // false')"
if [ "${PENDING_RETRYABLE}" -gt 0 ] && [ "${ANY_ACTIVE}" = "false" ]; then
  send_alert_once \
    "contract_jobs_pending_without_workers" \
    "⚠️ ${PENDING_RETRYABLE} retryable contract-jobs в очереди, но активные воркеры не обнаружены."
fi

if [ "${PENDING_EXHAUSTED_NEW}" -gt "${CONTRACT_EXHAUSTED_NEW_ALERT_THRESHOLD}" ]; then
  send_alert_once \
    "contract_jobs_exhausted_new_detected" \
    "⚠️ Обнаружено ${PENDING_EXHAUSTED_NEW} contract-jobs в статусе new с исчерпанными попытками (порог: ${CONTRACT_EXHAUSTED_NEW_ALERT_THRESHOLD})."
fi

if [ "${PROCESSING_STALE_COUNT}" -gt "${CONTRACT_STALE_PROCESSING_ALERT_THRESHOLD}" ]; then
  send_alert_once \
    "contract_jobs_stale_processing_detected" \
    "⚠️ Обнаружено ${PROCESSING_STALE_COUNT} stale contract-jobs в processing (порог: ${CONTRACT_STALE_PROCESSING_ALERT_THRESHOLD})."
fi

if [ "${FAILED_RETRYABLE_COUNT}" -gt "${CONTRACT_FAILED_RETRYABLE_ALERT_THRESHOLD}" ]; then
  send_alert_once \
    "contract_jobs_failed_retryable_detected" \
    "⚠️ В очереди ${FAILED_RETRYABLE_COUNT} failed contract-jobs, доступных для retry (порог: ${CONTRACT_FAILED_RETRYABLE_ALERT_THRESHOLD})."
fi

if [ "${SLA_ALERTS_ENABLED}" != "1" ]; then
  exit 0
fi

# 3) SLA: обязательные news-воркеры должны быть active
WORKERS_JSON="$(api_get "${API_BASE}/api/v1/workers/status")"
IFS=',' read -r -a REQUIRED_WORKERS_ARRAY <<<"${REQUIRED_NEWS_WORKERS}"
missing_workers=()
for worker_id in "${REQUIRED_WORKERS_ARRAY[@]}"; do
  trimmed="$(echo "${worker_id}" | xargs)"
  if [ -z "${trimmed}" ]; then
    continue
  fi
  active_count="$(echo "${WORKERS_JSON}" | jq -r --arg W "${trimmed}" '[.workers[] | select(.worker_id == $W and .active == true)] | length')"
  if [ "${active_count}" -eq 0 ]; then
    missing_workers+=("${trimmed}")
  fi
done
if [ "${#missing_workers[@]}" -gt 0 ]; then
  send_alert_once \
    "required_news_workers_inactive" \
    "⚠️ Неактивные news-воркеры: ${missing_workers[*]}."
fi

# 4) SLA: давно не было новых драфтов (review/scheduled)
REVIEW_JSON="$(api_get "${API_BASE}/api/v1/scheduled-posts?status=review&limit=100&newest_first=true")"
SCHEDULED_JSON="$(api_get "${API_BASE}/api/v1/scheduled-posts?status=scheduled&limit=100&newest_first=true")"
LATEST_CREATED_TS="$(
python3 - "$REVIEW_JSON" "$SCHEDULED_JSON" <<'PY'
import json, sys
review = json.loads(sys.argv[1] or "[]")
scheduled = json.loads(sys.argv[2] or "[]")
all_rows = list(review) + list(scheduled)
created = sorted([str(x.get("created_at") or "").strip() for x in all_rows if str(x.get("created_at") or "").strip()], reverse=True)
print(created[0] if created else "")
PY
)"
if [ -n "${LATEST_CREATED_TS}" ]; then
  age_hours="$(
python3 - "$LATEST_CREATED_TS" <<'PY'
from datetime import datetime, timezone
import sys
raw = sys.argv[1].replace("Z", "+00:00")
dt = datetime.fromisoformat(raw)
age = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
print(int(age.total_seconds() // 3600))
PY
)"
  if [ "${age_hours}" -ge "${DRAFT_MAX_IDLE_HOURS}" ]; then
    send_alert_once \
      "draft_idle_too_long" \
      "⚠️ Новые драфты не появлялись ${age_hours}ч (порог: ${DRAFT_MAX_IDLE_HOURS}ч)."
  fi
else
  send_alert_once \
    "draft_stream_empty" \
    "⚠️ В очереди review/scheduled нет ни одного поста. Проверьте генерацию."
fi

# 5) SLA: есть просроченные публикации (due queue)
DUE_COUNT="$(api_get "${API_BASE}/api/v1/scheduled-posts?due=true&limit=100" | jq -r 'length')"
if [ "${DUE_COUNT}" -gt "${DUE_POSTS_ALERT_THRESHOLD}" ]; then
  send_alert_once \
    "due_posts_threshold_exceeded" \
    "⚠️ Просроченных публикаций в очереди: ${DUE_COUNT} (порог: ${DUE_POSTS_ALERT_THRESHOLD})."
fi
