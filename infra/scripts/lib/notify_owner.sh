# shellcheck shell=bash
# Сообщение владельцу в Telegram — из скриптов на хосте Mac mini.
#
# С хоста api.telegram.org недоступен (Telegram в России заблокирован), и
# прямой запрос висит до таймаута: так сторож новостей (healthcheck.sh)
# месяцами «оповещал» в пустоту. Контейнеры ядра и бота ходят в Telegram
# через прокси (LEGAL_AI_HTTPS_PROXY) — сообщение уходит изнутри них, как у
# проверки после деплоя. Ядро лежит — пробуем контейнер бота.
#
#   . infra/scripts/lib/notify_owner.sh
#   notify_owner "текст"            # 0 — доставлено, 1 — нет
#
# Кому: NOTIFY_CHAT_ID, иначе ALERT_CHAT_ID, иначе ADMIN_TELEGRAM_ID. Каким
# ботом: ALERT_BOT_TOKEN, если задан, иначе токен бота-ассистента из
# контейнера. Токен и текст передаются через stdin, не в командной строке.

NOTIFY_CONTAINERS="${NOTIFY_CONTAINERS:-legal-ai-core-api legal-ai-lead-bot}"

_NOTIFY_PY='
import json, os, sys, urllib.request
d = json.load(sys.stdin)
token = d.get("token") or os.environ.get("LEAD_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or ""
chat = d.get("chat") or os.environ.get("ADMIN_TELEGRAM_ID") or ""
if not token or ":" not in token or not chat:
    sys.exit(2)
proxy = (os.environ.get("LEGAL_AI_HTTPS_PROXY") or "").strip()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": proxy, "http": proxy} if proxy else {}))
body = json.dumps({"chat_id": chat, "text": d["text"][:4000], "disable_web_page_preview": True}).encode()
req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body, headers={"Content-Type": "application/json"})
with opener.open(req, timeout=20) as r:
    sys.exit(0 if json.load(r).get("ok") else 1)
'

notify_owner() {
  local text="$1" payload container docker_bin
  docker_bin="${DOCKER_BIN:-$(command -v docker || echo /usr/local/bin/docker)}"
  payload="$(NOTIFY_TEXT="$text" NOTIFY_TOKEN="${ALERT_BOT_TOKEN:-}" \
    NOTIFY_CHAT="${NOTIFY_CHAT_ID:-${ALERT_CHAT_ID:-${ADMIN_TELEGRAM_ID:-}}}" \
    python3 -c 'import json, os; print(json.dumps({"text": os.environ["NOTIFY_TEXT"], "token": os.environ["NOTIFY_TOKEN"], "chat": os.environ["NOTIFY_CHAT"]}))')" || return 1
  for container in $NOTIFY_CONTAINERS; do
    if printf '%s' "$payload" | "$docker_bin" exec -i "$container" sh -c \
      'PY=/app/.venv/bin/python; [ -x "$PY" ] || PY="$(command -v python3 || command -v python)"; exec "$PY" -c "$0"' \
      "$_NOTIFY_PY" >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}
