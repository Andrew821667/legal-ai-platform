#!/bin/bash
#
# Регулярная проверка новостного контура с оповещением в Telegram.
#
# Запускать по расписанию. Раньше healthcheck.sh не был включён ни в cron, ни в
# launchd, поэтому об остановке генерации, пустой очереди и пропущенных
# публикациях никто не узнавал — проблемы всплывали только при ручной проверке.
#
# Переменные берутся из .env поимённо, а не через `source`: файл содержит
# значения с пробелами и скобками (поисковые запросы), и его исполнение
# в shell приводит к ошибкам.

set -uo pipefail

APP_DIR="${APP_DIR:-/Users/legalai/projects/legal-ai-platform}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"
NEEDED="API_KEY_ADMIN|ALERT_BOT_TOKEN|ALERT_CHAT_ID|TELEGRAM_API_HOST_IP"

cd "$APP_DIR" || exit 0

if [ -r "$ENV_FILE" ]; then
  while IFS= read -r line; do
    export "${line?}"
  done < <(grep -E "^(${NEEDED})=." "$ENV_FILE")
fi

# core-api слушает на локальном порту; внутри compose имя хоста недоступно.
export CORE_API_URL="${CORE_API_URL:-http://127.0.0.1:8100}"

exec bash "$APP_DIR/infra/scripts/healthcheck.sh"
