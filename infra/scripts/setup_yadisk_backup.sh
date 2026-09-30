#!/usr/bin/env bash
# Настройка зашифрованной копии бэкапов на Яндекс Диск. Запускает владелец, один раз:
#   ssh -t legalai-prod 'sudo -u andrej -i /Users/legalai/projects/legal-ai-platform/infra/scripts/setup_yadisk_backup.sh'
#
# Спрашивает логин Яндекса и пароль приложения для Диска (пароль не
# отображается), проверяет доступ (создаёт папку, пишет и удаляет пробный
# файл), сохраняет доступ в ~/.config/legalai/yadisk.netrc (права 600) и
# настройки в yadisk.env. Ключ шифрования создаёт один раз
# (~/.config/legalai/backup.key) и показывает его: сохраните в менеджере
# паролей — без него копии на Диске не расшифровать, если Mac mini пропадёт.
# Дальше ночной бэкап (backup_postgres.sh) сам шифрует и отправляет копию.
set -euo pipefail

CONF_DIR="$HOME/.config/legalai"
ENV_FILE="$CONF_DIR/yadisk.env"
NETRC="$CONF_DIR/yadisk.netrc"
KEY_FILE="$CONF_DIR/backup.key"
DAV="https://webdav.yandex.ru"

read -r -p "Логин Яндекса (без @yandex.ru): " login
login="${login%@yandex.ru}"
read -r -s -p "Пароль приложения для Диска (не отображается): " pass
echo
read -r -p "Папка на Диске [legalai-backups]: " dir
dir="${dir:-legalai-backups}"
if [ -z "$login" ] || [ -z "$pass" ]; then
  echo "Нужны логин и пароль приложения." >&2
  exit 1
fi
case "$pass" in *[[:space:]]*) pass="$(printf '%s' "$pass" | tr -d '[:space:]')" ;; esac

umask 077
mkdir -p "$CONF_DIR"
tmp_netrc="$(mktemp "$CONF_DIR/.netrc.XXXXXX")"
trap 'rm -f "$tmp_netrc"' EXIT
printf 'machine webdav.yandex.ru\nlogin %s\npassword %s\n' "$login" "$pass" > "$tmp_netrc"

echo "Проверяю доступ к Яндекс Диску…"
code="$(curl -s -o /dev/null -w '%{http_code}' --netrc-file "$tmp_netrc" --max-time 30 -X PROPFIND -H 'Depth: 0' "$DAV/")"
if [ "$code" = 401 ]; then
  echo "Яндекс не принял логин или пароль приложения. Пароль приложения — не основной пароль Яндекса." >&2
  exit 1
elif [ "$code" != 207 ]; then
  echo "Яндекс Диск ответил $code — попробуйте позже." >&2
  exit 1
fi
curl -s -o /dev/null --netrc-file "$tmp_netrc" --max-time 30 -X MKCOL "$DAV/$dir/" || true
probe=".legalai-write-test-$$"
probe_file="$(mktemp)"
printf ok > "$probe_file"
code="$(curl -s -o /dev/null -w '%{http_code}' --netrc-file "$tmp_netrc" --max-time 60 -T "$probe_file" "$DAV/$dir/$probe")"
rm -f "$probe_file"
curl -s -o /dev/null --netrc-file "$tmp_netrc" --max-time 30 -X DELETE "$DAV/$dir/$probe" || true
case "$code" in
  201 | 204) ;;
  507) echo "На Яндекс Диске нет места." >&2; exit 1 ;;
  *) echo "Записать на Диск не удалось (ответ $code)." >&2; exit 1 ;;
esac

mv "$tmp_netrc" "$NETRC"
chmod 600 "$NETRC"
trap - EXIT
{
  printf 'YADISK_DIR=%q\n' "$dir"
  printf 'YADISK_KEEP_DAYS=%q\n' "60"
} > "$ENV_FILE.tmp"
mv "$ENV_FILE.tmp" "$ENV_FILE"
chmod 600 "$ENV_FILE"

new_key=0
if [ ! -s "$KEY_FILE" ]; then
  openssl rand -base64 48 | tr -d '\n' > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  new_key=1
fi

echo
echo "Готово: доступ к Диску проверен, папка «$dir» создана."
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
