#!/usr/bin/env bash
# Проверка после деплоя: то, что уже ломалось незаметно.
#
# macmini_deploy_check.sh смотрит DNS, /health и логи — и только печатает.
# Сбои последних недель прошли мимо него: сайт не доходил до Telegram без
# прокси (документы клиентов не открывались), ядро — тоже; миграция могла не
# доехать. Здесь — ровно эти места, с повторами, и если что-то не так:
# сообщение владельцу в Telegram и ненулевой код (деплой в CI станет красным).
#
# Только чтение: ничего не меняет, кроме сообщения владельцу при сбое.
# SMOKE_NOTIFY=0 — не писать владельцу (ручной прогон).
set -uo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"
SMOKE_NOTIFY="${SMOKE_NOTIFY:-1}"
CORE="${CORE_CONTAINER:-legal-ai-core-api}"
WEB="${WEB_CONTAINER:-legal-ai-web}"
EXPECTED_SHA="${EXPECTED_SHA:-}"

env_value() {
  [ -r "$ENV_FILE" ] || return 0
  awk -F= -v key="$1" '$1 == key { sub(/^[^=]*=/, ""); gsub(/^[[:space:]]+|[[:space:]]+$/, ""); gsub(/^"|"$/, ""); print; exit }' "$ENV_FILE"
}

DOMAIN="${DOMAIN:-$(env_value DOMAIN)}"
DOMAIN="${DOMAIN:-ai-verdict.ru}"

failures=()

# Повтор: сеть и прокси иногда мигают — красный деплой из-за одного таймаута
# приучил бы не смотреть на красный.
check() {
  local title="$1"
  shift
  local attempt output
  for attempt in 1 2 3; do
    if output="$("$@" 2>&1)"; then
      echo "OK: $title${output:+ — $output}"
      return 0
    fi
    sleep $((attempt * 5))
  done
  echo "FAIL: $title — ${output:-нет ответа}"
  failures+=("$title: ${output:-нет ответа}")
  return 1
}

migrations_at_head() {
  local current heads
  current="$(docker exec -w /app/apps/core-api "$CORE" /app/.venv/bin/alembic current 2>/dev/null | tail -1)"
  heads="$(docker exec -w /app/apps/core-api "$CORE" /app/.venv/bin/alembic heads 2>/dev/null | tail -1)"
  [ -n "$current" ] && [ "${current%% *}" = "${heads%% *}" ] || { echo "в базе ${current:-?}, в коде ${heads:-?}"; return 1; }
  echo "${current%% *}"
}

core_reaches_telegram() {
  docker exec -i -w /app/apps/core-api "$CORE" /app/.venv/bin/python - <<'PY'
import sys
import requests
from core_api.config import get_settings, telegram_proxies
token = get_settings().lead_bot_token or ""
if not token:
    print("нет LEAD_BOT_TOKEN"); sys.exit(1)
try:
    ok = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10, proxies=telegram_proxies()).json().get("ok")
except Exception as exc:
    print(type(exc).__name__); sys.exit(1)
sys.exit(0 if ok else 1)
PY
}

web_reaches_telegram() {
  docker exec -i "$WEB" node - <<'JS'
const { fetch, ProxyAgent } = require("undici");
const proxy = (process.env.LEGAL_AI_HTTPS_PROXY || process.env.LEGAL_AI_HTTP_PROXY || "").trim();
const token = process.env.LEAD_BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN || "";
if (!token) { console.log("нет токена бота"); process.exit(1); }
fetch(`https://api.telegram.org/bot${token}/getMe`, {
  dispatcher: proxy ? new ProxyAgent(proxy) : undefined,
  signal: AbortSignal.timeout(10000),
})
  .then((r) => r.json())
  .then((j) => process.exit(j.ok ? 0 : 1))
  .catch((e) => { console.log(e.name); process.exit(1); });
JS
}

http_status() {
  local url="$1" expected="$2" code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url")"
  [ "$code" = "$expected" ] || { echo "ответ $code вместо $expected"; return 1; }
}

running_image() {
  local container="$1" image
  image="$(docker inspect -f '{{.State.Running}} {{.Config.Image}}' "$container" 2>/dev/null)" || { echo "контейнера нет"; return 1; }
  [ "${image%% *}" = "true" ] || { echo "не запущен"; return 1; }
  if [ -n "$EXPECTED_SHA" ] && [ "${image##*:}" != "$EXPECTED_SHA" ]; then
    echo "образ ${image##*:} вместо $EXPECTED_SHA"
    return 1
  fi
}

# Сайт после перезапуска ещё поднимается — ждём, пока станет healthy.
for _ in $(seq 1 30); do
  [ "$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}healthy{{end}}' "$WEB" 2>/dev/null)" = "healthy" ] && break
  sleep 3
done

echo "Проверка после деплоя (${EXPECTED_SHA:-без сверки версии})"
check "миграции базы на последней версии" migrations_at_head
check "ядро достаёт до Telegram через прокси" core_reaches_telegram
check "сайт достаёт до Telegram через прокси" web_reaches_telegram
check "главная страница сайта" http_status "https://$DOMAIN/" 200
check "рабочее место юриста открывается" http_status "https://$DOMAIN/lawyer" 200
check "кабинет клиента требует входа" http_status "https://$DOMAIN/api/client/summary" 401
for container in "$CORE" "$WEB" legal-ai-lead-bot legal-ai-news-publish; do
  check "контейнер $container запущен на новой версии" running_image "$container"
done

if [ "${#failures[@]}" -eq 0 ]; then
  echo "Проверка после деплоя: всё в порядке"
  exit 0
fi

echo "Проверка после деплоя: сбоев ${#failures[@]}"
if [ "$SMOKE_NOTIFY" = "1" ]; then
  text="После деплоя ${EXPECTED_SHA:0:7} что-то не так:"
  for item in "${failures[@]}"; do
    text+=$'\n'"— $item"
  done
  # Через ядро: у него токен и прокси. Ядро лежит — пробуем бота-ассистента.
  for container in "$CORE" legal-ai-lead-bot; do
    if printf '%s' "$text" | docker exec -i -e ADMIN_ID="$(env_value ADMIN_TELEGRAM_ID)" "$container" sh -c '
      PY=/app/.venv/bin/python; [ -x "$PY" ] || PY=python
      "$PY" -c "
import os, sys, requests
text = sys.stdin.read()
token = os.environ.get(\"LEAD_BOT_TOKEN\") or os.environ.get(\"TELEGRAM_BOT_TOKEN\") or \"\"
proxy = (os.environ.get(\"LEGAL_AI_HTTPS_PROXY\") or \"\").strip()
proxies = {\"https\": proxy, \"http\": proxy} if proxy else None
r = requests.post(f\"https://api.telegram.org/bot{token}/sendMessage\", data={\"chat_id\": os.environ.get(\"ADMIN_ID\") or os.environ.get(\"ADMIN_TELEGRAM_ID\"), \"text\": text}, timeout=15, proxies=proxies)
sys.exit(0 if r.json().get(\"ok\") else 1)
"' >/dev/null 2>&1; then
      echo "Владельцу отправлено сообщение о сбое"
      break
    fi
  done
fi
exit 1
