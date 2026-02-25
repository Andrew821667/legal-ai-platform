#!/bin/bash
set -euo pipefail

USAGE=$(df / --output=pcent | tail -1 | tr -d ' %')
if [ "$USAGE" -gt 85 ]; then
  if [ -n "${ALERT_BOT_TOKEN:-}" ] && [ -n "${ALERT_CHAT_ID:-}" ]; then
    curl -s "https://api.telegram.org/bot$ALERT_BOT_TOKEN/sendMessage" \
      -d "chat_id=$ALERT_CHAT_ID" \
      -d "text=⚠️ Диск заполнен на ${USAGE}%! Требуется очистка." >/dev/null
  fi
fi
