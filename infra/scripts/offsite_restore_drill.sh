#!/usr/bin/env bash
# Ежемесячные учения: восстановить последнюю копию с Яндекс Диска.
#
# Ночной бэкап (backup_postgres.sh) кладёт на Диск зашифрованный архив: дамп
# базы и база бота-ассистента. Копия, которую ни разу не восстанавливали, —
# надежда, а не бэкап: ключ мог смениться, архив — оказаться битым, дамп —
# не подняться новой версией Postgres. Здесь — весь путь аварии: скачать
# последний архив, расшифровать ключом с этой машины, сверить контрольные
# суммы, восстановить дамп во ВРЕМЕННЫЙ контейнер (restore_drill.sh, живая
# база только читается), проверить базу бота (sqlite integrity_check).
#
# Итог — владельцу в Telegram (lib/notify_owner.sh) и в service_health
# (key=restore_drill): ядро напомнит, если учения пропали больше чем на 40
# дней. Расшифрованные файлы лежат во временной папке и удаляются в любом
# случае: в них персональные данные клиентов.
#
# Запуск — launchd раз в месяц (infra/launchd/ru.legalai.restore-drill.plist),
# вручную: infra/scripts/offsite_restore_drill.sh (пользователь andrej).
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
YADISK_ENV="${YADISK_ENV:-$HOME/.config/legalai/yadisk.env}"
CONTAINER="${POSTGRES_CONTAINER:-legal-ai-postgres}"
PGUSER="${PGUSER:-legalai_app}"
PGDB="${PGDB:-legalai_platform}"
MAX_COPY_AGE_DAYS="${MAX_COPY_AGE_DAYS:-2}"

# shellcheck source=lib/notify_owner.sh
. "$ROOT_DIR/infra/scripts/lib/notify_owner.sh"
ADMIN_TELEGRAM_ID="${ADMIN_TELEGRAM_ID:-$(awk -F= '$1 == "ADMIN_TELEGRAM_ID" { print $2; exit }' "$ENV_FILE" 2>/dev/null)}"
export ADMIN_TELEGRAM_ID

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

record_health() {
  local ok="$1" error="$2" error_sql="NULL" failing="now()"
  [ -n "$error" ] && error_sql="'$(printf '%s' "${error:0:450}" | sed "s/'/''/g")'"
  [ "$ok" = true ] && failing="NULL"
  docker exec -i "$CONTAINER" psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 -q >/dev/null <<SQL || echo "WARN: не удалось записать итог учений" >&2
insert into service_health (key, ok, checked_at, failing_since, last_error, alerted_at)
values ('restore_drill', $ok, now(), $failing, $error_sql, NULL)
on conflict (key) do update set
  ok = excluded.ok,
  checked_at = excluded.checked_at,
  failing_since = case when excluded.ok then null else coalesce(service_health.failing_since, now()) end,
  last_error = excluded.last_error,
  alerted_at = null;
SQL
}

fail() {
  echo "FAIL: $1"
  record_health false "$1"
  notify_owner "🔴 Учения по восстановлению: копию с Яндекс Диска восстановить не удалось — $1.
Журнал: ~/backups/legal-ai/restore-drill.log на Mac mini (пользователь andrej)." || echo "WARN: сообщение владельцу не доставлено" >&2
  exit 1
}

if [ ! -r "$YADISK_ENV" ]; then
  fail "копия на Яндекс Диск не настроена (нет $YADISK_ENV)"
fi
# shellcheck disable=SC1090
. "$YADISK_ENV"
key="${YADISK_KEY_FILE:-$HOME/.config/legalai/backup.key}"
header="${YADISK_HEADER:-$HOME/.config/legalai/yadisk.header}"
[ -r "$key" ] && [ -r "$header" ] || fail "нет ключа шифрования или токена Диска"

yadisk_api() {
  local method="$1" path="$2"
  shift 2
  curl -s --max-time 60 -H @"$header" -X "$method" -G "https://cloud-api.yandex.net/v1/disk/resources$path" "$@"
}

name="$(yadisk_api GET "" --data-urlencode "path=app:/" --data-urlencode "limit=1000" \
  --data-urlencode "fields=_embedded.items.name" \
  | grep -o 'legal_ai_[0-9]\{8\}_[0-9]\{6\}\.tar\.enc' | sort -u | tail -1)"
[ -n "$name" ] || fail "на Диске нет ни одной копии (или токен Диска не принят)"
copy_day="${name:9:8}"
age_days=$(( ($(date +%s) - $(date -j -f %Y%m%d "$copy_day" +%s)) / 86400 ))
echo "Копия: $name (возраст ${age_days} дн.)"

href="$(yadisk_api GET /download --data-urlencode "path=app:/$name" | sed -n 's/.*"href":"\([^"]*\)".*/\1/p')"
[ -n "$href" ] || fail "Диск не дал ссылку на скачивание $name"
started=$(date +%s)
curl -sfL --max-time 1800 -o "$work/$name" "$href" && [ -s "$work/$name" ] || fail "не удалось скачать $name"
echo "Скачано за $(( $(date +%s) - started )) с ($(du -h "$work/$name" | cut -f1))"

"$ROOT_DIR/infra/scripts/decrypt_backup.sh" "$work/$name" "$key" >/dev/null 2>"$work/decrypt.err" \
  || fail "не удалось расшифровать или не сошлись контрольные суммы: $(tail -1 "$work/decrypt.err")"
dir="$work/${name%.tar.enc}"
dump="$(ls "$dir"/legal_ai_2*.dump 2>/dev/null | head -1)"
bot_db="$(ls "$dir"/legal_ai_bot_*.db 2>/dev/null | head -1)"
[ -n "$dump" ] || fail "в архиве нет дампа базы"

drill_out="$("$ROOT_DIR/infra/scripts/restore_drill.sh" "$dump" 2>&1)"
drill_rc=$?
echo "$drill_out"
[ "$drill_rc" -eq 0 ] || fail "дамп не восстановился: $(printf '%s\n' "$drill_out" | grep FAIL | tail -1)"

bot_note="базы бота в архиве нет"
if [ -n "$bot_db" ]; then
  integrity="$(sqlite3 "$bot_db" 'pragma integrity_check' 2>&1 | head -1)"
  [ "$integrity" = "ok" ] || fail "база бота повреждена: $integrity"
  bot_note="база бота цела"
fi

restore_seconds="$(printf '%s\n' "$drill_out" | sed -n 's/^Восстановлено за \([0-9]*\) с$/\1/p')"
leads="$(printf '%s\n' "$drill_out" | awk '$1 == "leads" { print $2 }')"
schema="$(printf '%s\n' "$drill_out" | sed -n 's/^Версия схемы: в бэкапе \([^,]*\),.*/\1/p')"
warning=""
[ "$age_days" -gt "$MAX_COPY_AGE_DAYS" ] && warning="
⚠️ Последней копии на Диске ${age_days} дн. — ночной бэкап на Диск, похоже, не идёт."

record_health true ""
notify_owner "✅ Учения по восстановлению прошли: копия с Яндекс Диска от ${copy_day:6:2}.${copy_day:4:2}.${copy_day:0:4} расшифрована и восстановлена во временную базу за ${restore_seconds:-?} с (обращений в ней: ${leads:-?}, схема ${schema:-?}); ${bot_note}.${warning}" \
  || echo "WARN: сообщение владельцу не доставлено" >&2
echo "OK: учения пройдены"
