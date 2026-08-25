#!/bin/zsh
set -u

LOG="${LEGAL_AI_BOTS_WATCHDOG_LOG:-/Users/andrej/Library/Logs/legal-ai-bots-watchdog.log}"
PROJECT_DIR="${PROJECT_DIR:-/Users/legalai/projects/legal-ai-platform}"
DOCKER="${DOCKER_BIN:-/usr/local/bin/docker}"
COMPOSE="${COMPOSE_BIN:-/opt/homebrew/bin/docker-compose}"
ENV_FILE="${COMPOSE_ENV_FILE:-$PROJECT_DIR/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/infra/compose/docker-compose.prod.yml}"
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-compose}"

TELEGRAM_CHECK_CONTAINER="${TELEGRAM_CHECK_CONTAINER:-legal-ai-lead-bot}"
TELEGRAM_CHECK_HOST="${TELEGRAM_CHECK_HOST:-api.telegram.org}"
BOT_STARTUP_GRACE_SECONDS="${BOT_STARTUP_GRACE_SECONDS:-90}"
PENDING_QUEUE_GRACE_SECONDS="${PENDING_QUEUE_GRACE_SECONDS:-240}"
QUEUE_RESTART_COOLDOWN_SECONDS="${QUEUE_RESTART_COOLDOWN_SECONDS:-600}"

TELEGRAM_SERVICES_RAW="${TELEGRAM_SERVICES:-lead-bot news-admin-bot news-reader-bot news-publish news-reader-digest}"
TELEGRAM_SERVICES=(${=TELEGRAM_SERVICES_RAW})
REQUIRED_SERVICES_RAW="${REQUIRED_SERVICES:-${TELEGRAM_SERVICES_RAW} news-generate news-telegram-ingest}"
REQUIRED_SERVICES=(${=REQUIRED_SERVICES_RAW})

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(ts) $*" >> "$LOG"; }

if [ -f "$LOG" ] && [ "$(wc -l < "$LOG" 2>/dev/null || echo 0)" -gt 4000 ]; then
  tail -1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

cd "$PROJECT_DIR" || { log "FAIL cd $PROJECT_DIR"; exit 1; }

compose() {
  "$COMPOSE" -p "$COMPOSE_PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

telegram_service_container() {
  local service
  service="$1"
  "$DOCKER" ps -q \
    --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
    --filter "label=com.docker.compose.service=$service" \
    | head -n 1
}

ensure_services_running() {
  local service running_id stopped_id
  local -a missing
  missing=()

  for service in "${REQUIRED_SERVICES[@]}"; do
    running_id="$(telegram_service_container "$service")"
    if [ -n "$running_id" ]; then
      continue
    fi

    stopped_id="$(
      "$DOCKER" ps -aq \
        --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
        --filter "label=com.docker.compose.service=$service" \
        | head -n 1
    )"
    if [ -n "$stopped_id" ]; then
      log "START_STOPPED_SERVICE service=$service"
      "$DOCKER" start "$stopped_id" >> "$LOG" 2>&1 || missing+=("$service")
    else
      missing+=("$service")
    fi
  done

  if [ "${#missing[@]}" -gt 0 ]; then
    log "CREATE_MISSING_SERVICES ${missing[*]}"
    compose up -d "${missing[@]}" >> "$LOG" 2>&1 || log "CREATE_MISSING_SERVICES_FAILED"
  else
    log "SERVICES_RUNNING"
  fi
}

check_tg_from_container() {
  "$DOCKER" exec "$TELEGRAM_CHECK_CONTAINER" python - "$TELEGRAM_CHECK_HOST" <<'PY'
import socket
import ssl
import sys

host = sys.argv[1]
try:
    sock = socket.create_connection((host, 443), timeout=8)
    with ssl.create_default_context().wrap_socket(sock, server_hostname=host) as tls:
        print(f"TG_CONTAINER_OK {tls.version()}")
except Exception as exc:
    print(f"TG_CONTAINER_FAIL {type(exc).__name__}: {exc}")
    raise SystemExit(1)
PY
}

container_age_seconds() {
  local started
  started="$("$DOCKER" inspect -f '{{.State.StartedAt}}' "$1" 2>/dev/null || true)"
  python3 - "$started" <<'PY'
import datetime
import sys
import time

value = sys.argv[1]
try:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    started = datetime.datetime.fromisoformat(value)
    print(max(0, int(time.time() - started.timestamp())))
except Exception:
    print(999999)
PY
}

telegram_pending_count() {
  local container_id token_env
  container_id="$1"
  token_env="$2"
  "$DOCKER" exec -i "$container_id" python - "$token_env" <<'PY'
import json
import os
import sys
import urllib.request

token = os.environ.get(sys.argv[1], "")
if not token:
    raise SystemExit(2)
with urllib.request.urlopen(
    f"https://api.telegram.org/bot{token}/getWebhookInfo",
    timeout=12,
) as response:
    payload = json.load(response)
if not payload.get("ok"):
    raise SystemExit(3)
print(int(payload.get("result", {}).get("pending_update_count", 0)))
PY
}

duplicate_poller_seen() {
  "$DOCKER" logs --since 10m "$1" 2>&1 \
    | /usr/bin/grep -qiE 'terminated by other getUpdates request|Conflict.*getUpdates'
}

queue_restart_allowed() {
  local state_file="$1" now last
  now="$(date +%s)"
  last="$(cat "$state_file" 2>/dev/null || echo 0)"
  if [ $((now - last)) -lt "$QUEUE_RESTART_COOLDOWN_SECONDS" ]; then
    return 1
  fi
  echo "$now" > "$state_file"
  return 0
}

ensure_telegram_queue_draining() {
  local service token_env container_id pending state_file restart_file
  local now first_seen previous_count age
  service="$1"
  token_env="$2"
  state_file="/tmp/legal-ai-${service}-pending.state"
  restart_file="/tmp/legal-ai-${service}-queue-restart.ts"
  container_id="$(telegram_service_container "$service")"
  if [ -z "$container_id" ]; then
    log "TG_QUEUE_CHECK_SKIPPED service=$service reason=container_missing"
    return
  fi

  age="$(container_age_seconds "$container_id")"
  if [ "$age" -lt "$BOT_STARTUP_GRACE_SECONDS" ]; then
    log "TG_QUEUE_CHECK_SKIPPED service=$service reason=warming age=${age}s"
    return
  fi

  pending="$(telegram_pending_count "$container_id" "$token_env" 2>/dev/null || true)"
  if ! [[ "$pending" =~ '^[0-9]+$' ]]; then
    log "TG_QUEUE_CHECK_FAILED service=$service"
    return
  fi
  if [ "$pending" -eq 0 ]; then
    rm -f "$state_file"
    log "TG_QUEUE_OK service=$service"
    return
  fi

  now="$(date +%s)"
  if [ ! -f "$state_file" ]; then
    echo "$now $pending" > "$state_file"
    log "TG_QUEUE_PENDING_FIRST service=$service count=$pending"
    return
  fi

  read -r first_seen previous_count < "$state_file"
  first_seen="${first_seen:-$now}"
  previous_count="${previous_count:-$pending}"
  if [ "$pending" -lt "$previous_count" ]; then
    echo "$now $pending" > "$state_file"
    log "TG_QUEUE_DRAINING service=$service count=$pending"
    return
  fi
  if [ $((now - first_seen)) -lt "$PENDING_QUEUE_GRACE_SECONDS" ]; then
    log "TG_QUEUE_PENDING_WAIT service=$service count=$pending"
    return
  fi

  if duplicate_poller_seen "$container_id"; then
    log "TG_DUPLICATE_POLLER_DETECTED service=$service action=manual_review"
    return
  fi
  if ! queue_restart_allowed "$restart_file"; then
    log "TG_QUEUE_RESTART_SKIPPED service=$service reason=cooldown"
    return
  fi

  log "TG_QUEUE_STALE_RESTART service=$service count=$pending"
  "$DOCKER" restart "$container_id" >> "$LOG" 2>&1 || {
    log "TG_QUEUE_RESTART_FAILED service=$service"
    return
  }
  rm -f "$state_file"
}

log "CHECK"
ensure_services_running

if check_tg_from_container >> "$LOG" 2>&1; then
  log "TG_CONTAINER_OK"
  ensure_telegram_queue_draining "lead-bot" "LEAD_BOT_TOKEN"
  ensure_telegram_queue_draining "news-admin-bot" "NEWS_ADMIN_BOT_TOKEN"
  ensure_telegram_queue_draining "news-reader-bot" "READER_BOT_TOKEN"
else
  log "TG_CONTAINER_UNREACHABLE action=wait_no_restart"
fi

"$DOCKER" ps --format 'table {{.Names}}\t{{.Status}}' \
  | egrep 'legal-ai-(lead-bot|news-admin-bot|news-reader-bot|news-publish|news-reader-digest|news-generate|news-telegram-ingest)' >> "$LOG" 2>&1 || true
log "DONE"
