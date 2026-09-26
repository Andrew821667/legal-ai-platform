#!/bin/bash
# Дамп базы в формате pg_dump -Fc. Хранит BACKUP_KEEP_DAYS дней.
#
# Запускается ежедневно launchd-агентом (infra/launchd/ru.legalai.postgres-backup.plist)
# и вручную перед рискованными изменениями. Проверить, что дамп
# восстанавливается, — infra/scripts/restore_drill.sh.
#
# Если настроен NAS (infra/scripts/setup_nas_backup.sh → ~/.config/legalai/nas.env),
# дамп копируется и туда: локальные дампы лежат на том же диске, что и база,
# и от потери машины не спасают. На NAS хранится NAS_KEEP_DAYS дней.
#
# Итог пишется в service_health (key=backup): ядро скажет владельцу, если
# свежего дампа нет больше суток или копия на NAS не удалась.
#
# Паспортные данные в дампе — шифротекст; ключ (PII_ENCRYPTION_KEY) хранится
# отдельно от бэкапов: ключ рядом с дампом = дамп открытым текстом.
set -uo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=${BACKUP_DIR:-$HOME/backups/legal-ai}
BACKUP_KEEP_DAYS=${BACKUP_KEEP_DAYS:-14}
NAS_ENV=${NAS_ENV:-$HOME/.config/legalai/nas.env}
mkdir -p "$BACKUP_DIR"
CONTAINER=${POSTGRES_CONTAINER:-legal-ai-postgres}
PGUSER=${PGUSER:-legalai_app}
PGDB=${PGDB:-legalai_platform}
TARGET="$BACKUP_DIR/legal_ai_$TIMESTAMP.dump"

# Состояние — в базу, которую бэкапим: ядро читает его в своём такте.
record_health() {
  local ok="$1" error="$2" dumped="$3" error_sql="NULL" checked="NULL" failing="now()"
  if [ -n "$error" ]; then
    error_sql="'$(printf '%s' "${error:0:450}" | sed "s/'/''/g")'"
  fi
  [ "$dumped" = 1 ] && checked="now()"
  [ "$ok" = true ] && failing="NULL"
  docker exec -i "$CONTAINER" psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 -q >/dev/null <<SQL || echo "WARN: не удалось записать состояние бэкапа" >&2
insert into service_health (key, ok, checked_at, failing_since, last_error, alerted_at)
values ('backup', $ok, $checked, $failing, $error_sql, NULL)
on conflict (key) do update set
  ok = excluded.ok,
  checked_at = coalesce(excluded.checked_at, service_health.checked_at),
  failing_since = case when excluded.ok then null else coalesce(service_health.failing_since, now()) end,
  last_error = excluded.last_error,
  alerted_at = case when excluded.ok then null else service_health.alerted_at end;
SQL
}

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

# Копия на NAS: подключить папку, скопировать через временное имя, сверить
# размер, убрать старые, отключить. Причина ошибки — текстом в stdout.
nas_copy() {
  local file="$1" mnt dest name part rc=0
  # shellcheck disable=SC1090
  . "$NAS_ENV"
  mnt="$HOME/mnt/legalai-nas"
  mkdir -p "$mnt"
  if ! mount | grep -q " on $mnt "; then
    if ! mount_smbfs "//$(urlencode "$NAS_USER"):$(urlencode "$NAS_PASS")@$NAS_HOST/$NAS_SHARE" "$mnt" 2>/dev/null; then
      echo "NAS $NAS_HOST недоступен или отказал в подключении"
      return 1
    fi
  fi
  dest="$mnt/${NAS_DIR:-legal-ai-platform}"
  name="$(basename "$file")"
  part="$dest/.$name.part"
  if ! mkdir -p "$dest" || ! cp "$file" "$part" || ! mv "$part" "$dest/$name"; then
    echo "не удалось записать дамп на NAS"
    rc=1
  elif [ "$(stat -f %z "$file")" != "$(stat -f %z "$dest/$name")" ]; then
    echo "размер копии на NAS не совпал с дампом"
    rc=1
  else
    find "$dest" -name 'legal_ai_*.dump' -mtime +"${NAS_KEEP_DAYS:-60}" -delete
  fi
  umount "$mnt" >/dev/null 2>&1 || true
  return "$rc"
}

# Во временный файл: оборванный дамп не должен выглядеть как свежий бэкап.
if ! docker exec "$CONTAINER" pg_dump -U "$PGUSER" -Fc "$PGDB" > "$TARGET.part" || [ ! -s "$TARGET.part" ]; then
  rm -f "$TARGET.part"
  echo "Backup FAILED: pg_dump" >&2
  record_health false "дамп базы не удался" 0
  exit 1
fi
mv "$TARGET.part" "$TARGET"
chmod 600 "$TARGET"
find "$BACKUP_DIR" -name 'legal_ai_*.dump' -mtime +"$BACKUP_KEEP_DAYS" -delete
echo "Backup completed: $(basename "$TARGET") ($(du -h "$TARGET" | cut -f1))"

if [ -r "$NAS_ENV" ]; then
  if nas_error="$(nas_copy "$TARGET")"; then
    echo "NAS copy completed"
    record_health true "" 1
  else
    echo "NAS copy FAILED: $nas_error" >&2
    record_health false "копия на NAS не удалась: $nas_error" 1
    exit 1
  fi
else
  record_health true "" 1
fi
