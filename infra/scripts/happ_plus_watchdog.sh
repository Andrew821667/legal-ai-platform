#!/bin/zsh
# Observe Happ Plus without changing the active proxy-balancer routes.
# Automatic connection is opt-in via HAPP_AUTO_START=1 because enabling the
# tunnel can conflict with the host-level Xray balancer.

set -u

LOG="${HAPP_WATCHDOG_LOG:-/Users/andrej/Library/Logs/happ-plus-watchdog.log}"
SERVICE_NAME="${HAPP_SERVICE_NAME:-Happ Plus}"
STATE_FILE="${HAPP_WATCHDOG_STATE:-/tmp/happ-plus-watchdog.state}"
PREFERENCES_FILE="${HAPP_PREFERENCES_FILE:-/Users/andrej/Library/Group Containers/group.su.ffg.happ.plus/Library/Preferences/group.su.ffg.happ.plus.plist}"
AUTO_START="${HAPP_AUTO_START:-0}"
# How long to wait after `scutil --nc start` before re-checking status.
START_GRACE_SECONDS="${HAPP_START_GRACE_SECONDS:-8}"
# Suppress repeated identical log lines: only re-log status if it
# changed since last run, OR every Nth tick.
QUIET_REPEAT_TICKS="${HAPP_QUIET_REPEAT_TICKS:-30}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(ts) $*" >> "$LOG"; }

read_vpn_state() {
  # Output: "Connected", "Disconnected", or "Unknown".
  local raw
  raw="$(scutil --nc status "$SERVICE_NAME" 2>/dev/null | head -n 1)"
  if [ -z "$raw" ]; then
    echo "Unknown"
    return
  fi
  echo "$raw"
}

# Read state: "last_state:repeat_count"
prev_vpn_state="Unknown"
prev_repeat=0
if [ -r "$STATE_FILE" ]; then
  state_line="$(cat "$STATE_FILE" 2>/dev/null || echo '')"
  prev_vpn_state="${state_line%%:*}"
  rest="${state_line#*:}"
  if [ "$rest" != "$state_line" ]; then
    prev_repeat="$rest"
  fi
fi

vpn_state="$(read_vpn_state)"

# Suppress noisy logs: only log when state changes, or every Nth tick.
should_log=1
if [ "$vpn_state" = "$prev_vpn_state" ]; then
  prev_repeat=$((prev_repeat + 1))
  if [ "$prev_repeat" -lt "$QUIET_REPEAT_TICKS" ]; then
    should_log=0
  else
    prev_repeat=0
  fi
else
  prev_repeat=0
fi

if [ "$should_log" -eq 1 ]; then
  log "STATUS $vpn_state"
fi

if [ "$vpn_state" = "Connected" ]; then
  echo "${vpn_state}:${prev_repeat}" > "$STATE_FILE"
  exit 0
fi

# The current production network uses the standalone proxy balancer. Merely
# observing a disconnected Happ service must not rewrite that network state.
if [ "$AUTO_START" != "1" ]; then
  if [ "$should_log" -eq 1 ]; then
    log "MONITOR_ONLY auto_start=disabled"
  fi
  echo "${vpn_state}:${prev_repeat}" > "$STATE_FILE"
  exit 0
fi

# Happ can lose its active config after a subscription refresh. Starting an
# empty tunnel briefly breaks host DNS, so wait for an explicit profile choice.
if ! plutil -extract connectedConfigJson raw -o - "$PREFERENCES_FILE" >/dev/null 2>&1; then
  if [ "$should_log" -eq 1 ]; then
    log "WAITING_FOR_ACTIVE_CONFIG"
  fi
  echo "${vpn_state}:${prev_repeat}" > "$STATE_FILE"
  exit 0
fi

log "STARTING service=\"$SERVICE_NAME\""
scutil --nc start "$SERVICE_NAME" >> "$LOG" 2>&1 || true
sleep "$START_GRACE_SECONDS"

post_vpn_state="$(read_vpn_state)"
log "POST_START $post_vpn_state"

# Reset repeat counter on transition.
echo "${post_vpn_state}:0" > "$STATE_FILE"

if [ "$post_vpn_state" = "Connected" ]; then
  exit 0
fi
exit 1
