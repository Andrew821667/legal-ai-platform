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
RECOVERY_COOLDOWN_SECONDS="${RECOVERY_COOLDOWN_SECONDS:-300}"
RECOVERY_STATE_FILE="${RECOVERY_STATE_FILE:-/tmp/legal-ai-bots-watchdog-recovery.ts}"
STOP_HAPP_TUNNEL="${STOP_HAPP_TUNNEL:-1}"
STOP_HAPP_APP="${STOP_HAPP_APP:-0}"

TELEGRAM_SERVICES_RAW="${TELEGRAM_SERVICES:-lead-bot news-admin-bot news-reader-bot news-publish news-reader-digest}"
TELEGRAM_SERVICES=(${=TELEGRAM_SERVICES_RAW})

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(ts) $*" >> "$LOG"; }

cd "$PROJECT_DIR" || { log "FAIL cd $PROJECT_DIR"; exit 1; }

compose() {
  "$COMPOSE" -p "$COMPOSE_PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
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

route_interface() {
  route get "$TELEGRAM_CHECK_HOST" 2>/dev/null | awk '/interface:/{print $2; exit}'
}

recovery_allowed() {
  local now last
  now="$(date +%s)"
  if [ -f "$RECOVERY_STATE_FILE" ]; then
    last="$(cat "$RECOVERY_STATE_FILE" 2>/dev/null || echo 0)"
  else
    last=0
  fi
  if [ $((now - last)) -lt "$RECOVERY_COOLDOWN_SECONDS" ]; then
    return 1
  fi
  echo "$now" > "$RECOVERY_STATE_FILE"
  return 0
}

stop_happ_tunnel_if_route_is_tun() {
  local iface
  iface="$(route_interface || true)"
  log "ROUTE_INTERFACE ${iface:-unknown}"
  if [ "$STOP_HAPP_TUNNEL" != "1" ]; then
    return 0
  fi
  case "$iface" in
    utun*)
      log "STOP_HAPP_TUNNEL_BEGIN"
      pkill -f "/Applications/Happ Plus.app/Contents/PlugIns/Tunnel.appex" >/dev/null 2>&1 || true
      if [ "$STOP_HAPP_APP" = "1" ]; then
        pkill -f "/Applications/Happ Plus.app/Contents/MacOS/Happ" >/dev/null 2>&1 || true
      fi
      sleep 5
      log "STOP_HAPP_TUNNEL_DONE"
      ;;
  esac
}

restart_telegram_services() {
  log "RESTART_TELEGRAM_SERVICES ${TELEGRAM_SERVICES[*]}"
  compose restart "${TELEGRAM_SERVICES[@]}" >> "$LOG" 2>&1 || log "RESTART_TELEGRAM_SERVICES_FAILED"
}

ensure_services_running() {
  local stopped need
  stopped="$(
    compose ps --status exited --status restarting --services 2>/dev/null \
      | egrep '^(lead-bot|news-admin-bot|news-reader-bot|news-publish|news-reader-digest)$' || true
  )"
  if [ -n "$stopped" ]; then
    need=("${(@f)stopped}")
  else
    need=()
  fi

  if [ "${#need[@]}" -gt 0 ]; then
    log "RESTART_STOPPED_SERVICES ${need[*]}"
    compose restart "${need[@]}" >> "$LOG" 2>&1 || log "RESTART_STOPPED_SERVICES_FAILED"
  else
    log "SERVICES_RUNNING"
  fi
}

log "CHECK"

if check_tg_from_container >> "$LOG" 2>&1; then
  log "TG_CONTAINER_OK"
else
  log "TG_CONTAINER_FAIL_FIRST"
  if recovery_allowed; then
    stop_happ_tunnel_if_route_is_tun
    if check_tg_from_container >> "$LOG" 2>&1; then
      log "TG_OK_AFTER_ROUTE_RECOVERY"
      restart_telegram_services
    else
      log "TG_STILL_FAIL_AFTER_ROUTE_RECOVERY"
      restart_telegram_services
      sleep 5
      if check_tg_from_container >> "$LOG" 2>&1; then
        log "TG_OK_AFTER_SERVICE_RESTART"
      else
        log "TG_FAIL_AFTER_ALL_RECOVERY"
      fi
    fi
  else
    log "RECOVERY_SKIPPED_COOLDOWN"
  fi
fi

ensure_services_running

"$DOCKER" ps --format 'table {{.Names}}\t{{.Status}}' \
  | egrep 'legal-ai-(lead-bot|news-admin-bot|news-reader-bot|news-publish|news-reader-digest)' >> "$LOG" 2>&1 || true
log "DONE"
