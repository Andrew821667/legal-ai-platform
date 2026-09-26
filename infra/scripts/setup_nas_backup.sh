#!/usr/bin/env bash
# Настройка копии бэкапов на NAS. Запускает владелец, один раз:
#   ssh -t legalai-prod 'sudo -u andrej -i /Users/legalai/projects/legal-ai-platform/infra/scripts/setup_nas_backup.sh'
#
# Спрашивает адрес NAS, общую папку, пользователя и пароль (пароль не
# отображается), сохраняет их в ~/.config/legalai/nas.env с правами 600 и
# проверяет: подключает папку, пишет и удаляет пробный файл, отключает.
# Дальше ночной бэкап (backup_postgres.sh) сам копирует дамп на NAS.
#
# На NAS лучше завести отдельного пользователя с доступом только к этой папке:
# этот пароль хранится на Mac mini.
set -euo pipefail

CONF_DIR="$HOME/.config/legalai"
ENV_FILE="$CONF_DIR/nas.env"

urlencode() {
  # Побайтно через od: в bash 3.2 (macOS) printf "'c" портит байты не-ASCII.
  local out="" hex
  for hex in $(printf '%s' "$1" | od -An -v -tx1); do
    case "$hex" in
      3[0-9] | 4[1-9a-f] | 5[0-9a] | 6[1-9a-f] | 7[0-9a] | 2d | 2e | 5f | 7e)
        out+=$(printf "\\$(printf '%03o' "0x$hex")") ;;
      *) out+="%$(printf '%s' "$hex" | tr 'a-f' 'A-F')" ;;
    esac
  done
  printf '%s' "$out"
}

read -r -p "Адрес NAS [192.168.0.83]: " host
host="${host:-192.168.0.83}"
read -r -p "Общая папка на NAS [legalai-backups]: " share
share="${share:-legalai-backups}"
read -r -p "Пользователь NAS: " user
read -r -s -p "Пароль (не отображается): " pass
echo
if [ -z "$user" ] || [ -z "$pass" ]; then
  echo "Нужны пользователь и пароль." >&2
  exit 1
fi

mnt="$(mktemp -d)"
cleanup() { umount "$mnt" >/dev/null 2>&1 || true; rmdir "$mnt" 2>/dev/null || true; }
trap cleanup EXIT

echo "Проверяю подключение к //$host/$share…"
if ! mount_smbfs "//$(urlencode "$user"):$(urlencode "$pass")@$host/$share" "$mnt"; then
  echo "Не удалось подключить папку: проверьте адрес, имя папки, пользователя и пароль." >&2
  exit 1
fi
probe="$mnt/.legalai-write-test-$$"
if ! echo ok > "$probe" || ! rm -f "$probe"; then
  echo "Папка подключилась, но записать в неё нельзя: дайте пользователю право на запись." >&2
  exit 1
fi

umask 077
mkdir -p "$CONF_DIR"
{
  printf 'NAS_HOST=%q\n' "$host"
  printf 'NAS_SHARE=%q\n' "$share"
  printf 'NAS_USER=%q\n' "$user"
  printf 'NAS_PASS=%q\n' "$pass"
  printf 'NAS_DIR=%q\n' "legal-ai-platform"
  printf 'NAS_KEEP_DAYS=%q\n' "60"
} > "$ENV_FILE.tmp"
mv "$ENV_FILE.tmp" "$ENV_FILE"
chmod 600 "$ENV_FILE"
echo "Готово: папка доступна для записи, настройки сохранены в $ENV_FILE (права 600)."
echo "Следующий ночной бэкап скопирует дамп на NAS. Проверить сейчас:"
echo "  sudo launchctl kickstart -k system/ru.legalai.postgres-backup && tail ~/backups/legal-ai/backup.log"
