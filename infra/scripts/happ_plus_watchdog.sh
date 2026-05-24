#!/bin/zsh
# Keep the Happ Plus VPN service Connected on the Mac Mini.
#
# Why: news-telegram-ingest reads public Telegram channels via the
# t.me/s/<channel> HTML preview through the host's xray HTTP proxy
# (default :10808). The proxy only has a route to t.me while Happ Plus
# is Connected. If Happ Plus is Disconnected (after reboot, crash, or
# because bots_watchdog.sh deliberately stopped the tunnel to bring
# api.telegram.org back onto the direct route), the HTML path goes
# empty and ingest silently falls back to the user-session Telethon
# path — which is exactly the user-account-ban risk we built the HTML
# path to avoid.
#
# This watcher runs every minute via launchd (see
# ~/Library/LaunchAgents/ru.legalai.happ-plus.watchdog.plist). It checks
# the VPN status and starts it if needed. It does *not* try to reason
# about why Happ Plus is down — that's bots_watchdog.sh's job. It just
# brings the proxy back so that the next ingest tick uses HTML again.

set -u

LOG="${HAPP_WATCHDOG_LOG:-/Users/andrej/Library/Logs/happ-plus-watchdog.log}"
SERVICE_NAME="${HAPP_SERVICE_NAME:-Happ Plus}"
STATE_FILE="${HAPP_WATCHDOG_STATE:-/tmp/happ-plus-watchdog.state}"
# How long to wait after `scutil --nc start` before re-checking status.
START_GRACE_SECONDS="${HAPP_START_GRACE_SECONDS:-8}"
# Suppress repeated identical log lines: only re-log status if it
# changed since last run, OR every Nth tick.
QUIET_REPEAT_TICKS="${HAPP_QUIET_REPEAT_TICKS:-30}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(ts) $*" >> "$LOG"; }

vpn_status() {
  # Output: "Connected", "Disconnected", or "Unknown".
  local raw
  raw="$(scutil --nc status "$SERVICE_NAME" 2>/dev/null | head -n 1)"
  if [ -z "$raw" ]; then
    echo "Unknown"
    return
  fi
  echo "$raw"
}

# Read state: "last_status:repeat_count"
prev_status="Unknown"
prev_repeat=0
if [ -r "$STATE_FILE" ]; then
  state_line="$(cat "$STATE_FILE" 2>/dev/null || echo '')"
  prev_status="${state_line%%:*}"
  rest="${state_line#*:}"
  if [ "$rest" != "$state_line" ]; then
    prev_repeat="$rest"
  fi
fi

status="$(vpn_status)"

# Suppress noisy logs: only log when status changes, or every Nth tick.
should_log=1
if [ "$status" = "$prev_status" ]; then
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
  log "STATUS $status"
fi

if [ "$status" = "Connected" ]; then
  echo "${status}:${prev_repeat}" > "$STATE_FILE"
  exit 0
fi

# Anything other than Connected — try to bring it up.
log "STARTING service=\"$SERVICE_NAME\""
scutil --nc start "$SERVICE_NAME" >> "$LOG" 2>&1 || true
sleep "$START_GRACE_SECONDS"

post_status="$(vpn_status)"
log "POST_START $post_status"

# Reset repeat counter on transition.
echo "${post_status}:0" > "$STATE_FILE"

if [ "$post_status" = "Connected" ]; then
  exit 0
fi
exit 1
