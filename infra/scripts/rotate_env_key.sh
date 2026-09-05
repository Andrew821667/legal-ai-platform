#!/bin/bash
# Замена секрета в боевом .env.
#
# Пишет через усечение существующего файла, а не пересоздаёт его: пересоздание
# сбрасывает ACL (user:andrej allow read), без которого деплой не может
# прочитать .env и падает с permission denied. Это уже случалось дважды.
#
# Использование:  ./rotate_env_key.sh [ИМЯ_ПЕРЕМЕННОЙ]
# По умолчанию — INTAKE_ANALYSIS_API_KEY.
#
# На боевом хосте лежит копия в ~/rotate-env-key.sh. Версия здесь —
# источник: копия на машине переживёт не всё, а runbook на неё ссылается.

set -euo pipefail

ENV_FILE="$HOME/projects/legal-ai-platform/.env"
VAR="${1:-INTAKE_ANALYSIS_API_KEY}"

[ -f "$ENV_FILE" ] || { echo "не найден $ENV_FILE"; exit 1; }
grep -q "^${VAR}=" "$ENV_FILE" || { echo "в .env нет строки ${VAR}="; exit 1; }

echo "Файл:      $ENV_FILE"
echo "Переменная: $VAR"
echo -n "Сейчас:     "
grep "^${VAR}=" "$ENV_FILE" | sed -E 's/=(.{7}).*(.{4})$/=\1…\2/'
echo

read -rsp "Новое значение (ввод скрыт): " NEWVAL
echo
[ -n "$NEWVAL" ] || { echo "пусто — ничего не менял"; exit 1; }

BACKUP="${ENV_FILE}.bak-$(date +%Y%m%d-%H%M%S)"
cp -p "$ENV_FILE" "$BACKUP"

VAR="$VAR" NEWVAL="$NEWVAL" python3 - "$ENV_FILE" <<'PY'
import os, pathlib, sys
path = pathlib.Path(sys.argv[1])
name = os.environ['VAR']
value = os.environ['NEWVAL'].strip()
out, found = [], False
for line in path.read_text(encoding='utf-8').splitlines(keepends=True):
    if line.startswith(name + '='):
        out.append(name + '=' + value + '\n'); found = True
    else:
        out.append(line)
if not found:
    raise SystemExit('строка не найдена — ничего не менял')
# Открытие на запись усекает файл, не пересоздавая его: inode тот же,
# значит права и ACL остаются.
with path.open('w', encoding='utf-8') as fh:
    fh.writelines(out)
PY

unset NEWVAL
echo
echo "Готово. Стало:"
grep "^${VAR}=" "$ENV_FILE" | sed -E 's/=(.{7}).*(.{4})$/=\1…\2/'
echo
echo "Права и ACL:"
ls -le "$ENV_FILE" | head -3
echo
echo "Копия: $BACKUP  (удалите, когда убедитесь, что всё работает)"
echo "Дальше нужен перезапуск core-api — настройки читаются при старте."
