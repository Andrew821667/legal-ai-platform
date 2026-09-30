#!/usr/bin/env bash
# Настройка зашифрованной копии бэкапов на Яндекс Диск. Запускает владелец, один раз:
#   ssh -t legalai-prod 'sudo -u andrej -i /Users/legalai/projects/legal-ai-platform/infra/scripts/setup_yadisk_backup.sh'
#
# Нужен OAuth-токен приложения Яндекса с единственным доступом «Доступ к папке
# приложения на Диске» (как выпустить — docs/runbook.md, «Копия на Яндекс
# Диск»): WebDAV Яндекс оставил только платным тарифам, а REST API с таким
# токеном видит одну свою папку («Приложения/<имя приложения>»), не весь Диск.
#
# Спрашивает токен (не отображается), проверяет запись (кладёт и удаляет
# пробный файл), сохраняет токен в ~/.config/legalai/yadisk.header (права
# 600) и настройки в yadisk.env. Ключ шифрования создаёт один раз
# (~/.config/legalai/backup.key) и показывает его: сохраните в менеджере
# паролей — без него копии на Диске не расшифровать, если Mac mini пропадёт.
# Дальше ночной бэкап (backup_postgres.sh) сам шифрует и отправляет копию.
set -euo pipefail

CONF_DIR="$HOME/.config/legalai"
ENV_FILE="$CONF_DIR/yadisk.env"
HEADER="$CONF_DIR/yadisk.header"
KEY_FILE="$CONF_DIR/backup.key"
API="https://cloud-api.yandex.net/v1/disk/resources"

read -r -s -p "Токен Яндекс Диска (не отображается): " token
echo
token="$(printf '%s' "$token" | tr -d '[:space:]')"
if [ -z "$token" ]; then
  echo "Нужен токен." >&2
  exit 1
fi

umask 077
mkdir -p "$CONF_DIR"
tmp_header="$(mktemp "$CONF_DIR/.header.XXXXXX")"
probe_file="$(mktemp)"
trap 'rm -f "$tmp_header" "$probe_file"' EXIT
printf 'Authorization: OAuth %s\n' "$token" > "$tmp_header"

echo "Проверяю запись на Яндекс Диск…"
probe="app:/.legalai-write-test-$$"
link="$(curl -s --max-time 30 -H @"$tmp_header" -G "$API/upload" --data-urlencode "path=$probe" --data-urlencode "overwrite=true")"
href="$(printf '%s' "$link" | sed -n 's/.*"href":"\([^"]*\)".*/\1/p')"
if [ -z "$href" ]; then
  case "$link" in
    *UnauthorizedError*) echo "Яндекс не принял токен: выпустите новый (см. runbook)." >&2 ;;
    *InsufficientStorage*) echo "На Яндекс Диске нет места." >&2 ;;
    *) echo "Яндекс Диск не дал ссылку на загрузку: $(printf '%s' "$link" | head -c 200)" >&2 ;;
  esac
  exit 1
fi
printf ok > "$probe_file"
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 -T "$probe_file" "$href")"
curl -s -o /dev/null --max-time 30 -H @"$tmp_header" -X DELETE -G "$API" \
  --data-urlencode "path=$probe" --data-urlencode "permanently=true" || true
case "$code" in
  201 | 202) ;;
  507) echo "На Яндекс Диске нет места." >&2; exit 1 ;;
  *) echo "Записать на Диск не удалось (ответ $code)." >&2; exit 1 ;;
esac

mv "$tmp_header" "$HEADER"
chmod 600 "$HEADER"
printf 'YADISK_KEEP_DAYS=%q\n' "60" > "$ENV_FILE.tmp"
mv "$ENV_FILE.tmp" "$ENV_FILE"
chmod 600 "$ENV_FILE"

new_key=0
if [ ! -s "$KEY_FILE" ]; then
  openssl rand -base64 48 | tr -d '\n' > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  new_key=1
fi

echo
echo "Готово: запись на Диск проверена. Копии будут в папке «Приложения» на Диске."
if [ "$new_key" = 1 ]; then
  echo
  echo "Ключ шифрования бэкапов — СОХРАНИТЕ ЕГО В МЕНЕДЖЕРЕ ПАРОЛЕЙ (показывается один раз):"
  echo
  cat "$KEY_FILE"
  echo
  echo
  echo "Без этого ключа копии на Диске не расшифровать, если Mac mini пропадёт."
else
  echo "Ключ шифрования уже был создан раньше — он не менялся."
fi
echo "Следующий ночной бэкап отправит копию на Диск. Проверить сейчас:"
echo "  sudo launchctl kickstart -k system/ru.legalai.postgres-backup && tail ~/backups/legal-ai/backup.log"
