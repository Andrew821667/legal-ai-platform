#!/bin/bash
#
# Держит доступ деплоя к боевому .env.
#
# Файл принадлежит legalai и закрыт правами 600, а деплой ходит под andrej,
# поэтому доступ выдан отдельной записью ACL. Любая перезапись файла (sed -i,
# редактор, установка нового значения) пересоздаёт его и стирает ACL — после
# этого деплой падает на этапе чтения переменных:
#
#   open /Users/legalai/projects/legal-ai-platform/.env: permission denied
#
# Проверка дешёвая, поэтому запускается по расписанию: восстановить запись
# заранее дешевле, чем разбираться в упавшем деплое.

set -uo pipefail

ENV_FILE="${ENV_FILE:-/Users/legalai/projects/legal-ai-platform/.env}"
DEPLOY_USER="${DEPLOY_USER:-andrej}"

[ -f "$ENV_FILE" ] || exit 0

# ACL уже на месте — ничего не делаем и молчим, чтобы не засорять лог.
if ls -le "$ENV_FILE" | grep -q "user:${DEPLOY_USER} allow read"; then
  exit 0
fi

if chmod +a "user:${DEPLOY_USER} allow read" "$ENV_FILE" 2>/dev/null; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') восстановлен доступ ${DEPLOY_USER} к $(basename "$ENV_FILE")"
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') НЕ УДАЛОСЬ восстановить ACL на $ENV_FILE" >&2
  exit 1
fi
