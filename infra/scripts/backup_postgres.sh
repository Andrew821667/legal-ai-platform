#!/bin/bash
# Дамп базы в формате pg_dump -Fc. Хранит BACKUP_KEEP_DAYS дней.
#
# Запускается ежедневно launchd-агентом (infra/launchd/ru.legalai.postgres-backup.plist)
# и вручную перед рискованными изменениями. Проверить, что дамп
# восстанавливается, — infra/scripts/restore_drill.sh.
#
# Рядом с дампом — копия базы бота-ассистента (bot.db в контейнере
# legal-ai-lead-bot: пользователи бота, состояние диалогов, отметки о согласиях).
#
# Если настроен NAS (infra/scripts/setup_nas_backup.sh → ~/.config/legalai/nas.env),
# дамп копируется и туда: локальные дампы лежат на том же диске, что и база,
# и от потери машины не спасают. На NAS хранится NAS_KEEP_DAYS дней.
#
# Если настроен Яндекс Диск (infra/scripts/setup_yadisk_backup.sh →
# ~/.config/legalai/yadisk.env), дамп и база бота уходят туда одним архивом,
# зашифрованным на этой машине, в папку приложения («Приложения» на Диске):
# на Диске только шифротекст. Хранится YADISK_KEEP_DAYS дней. Расшифровать —
# infra/scripts/decrypt_backup.sh.
#
# Итог пишется в service_health (key=backup): ядро скажет владельцу, если
# свежего дампа нет больше суток или копия (бот, NAS, Диск) не удалась.
#
# Паспортные данные в дампе — шифротекст; ключ (PII_ENCRYPTION_KEY) хранится
# отдельно от бэкапов: ключ рядом с дампом = дамп открытым текстом.
set -uo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=${BACKUP_DIR:-$HOME/backups/legal-ai}
BACKUP_KEEP_DAYS=${BACKUP_KEEP_DAYS:-14}
NAS_ENV=${NAS_ENV:-$HOME/.config/legalai/nas.env}
YADISK_ENV=${YADISK_ENV:-$HOME/.config/legalai/yadisk.env}
BOT_CONTAINER=${BOT_CONTAINER:-legal-ai-lead-bot}
BOT_DB_PATH=${BOT_DB_PATH:-/app/data/bot.db}
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

# База бота — SQLite внутри контейнера: снимаем согласованную копию его же
# Python (backup API, база открыта только на чтение) и забираем наружу.
bot_db_copy() {
  local target="$1" tmp="/tmp/legal_ai_bot_backup.db"
  if ! docker exec "$BOT_CONTAINER" python -c "import sqlite3; s = sqlite3.connect('file:$BOT_DB_PATH?mode=ro', uri=True); d = sqlite3.connect('$tmp'); s.backup(d); d.close(); s.close()" >/dev/null 2>&1; then
    echo "не удалось снять копию $BOT_DB_PATH в $BOT_CONTAINER"
    return 1
  fi
  if ! docker cp "$BOT_CONTAINER:$tmp" "$target.part" >/dev/null 2>&1 || [ ! -s "$target.part" ]; then
    rm -f "$target.part"
    docker exec "$BOT_CONTAINER" rm -f "$tmp" >/dev/null 2>&1 || true
    echo "не удалось забрать копию базы бота из контейнера"
    return 1
  fi
  docker exec "$BOT_CONTAINER" rm -f "$tmp" >/dev/null 2>&1 || true
  mv "$target.part" "$target"
  chmod 600 "$target"
}

# Копия на Яндекс Диск — REST API (WebDAV Яндекс оставил только платным
# тарифам). Токен OAuth с доступом только к папке приложения: он не видит
# остальных файлов Диска. Дамп и база бота — в один tar с контрольными
# суммами (SHA256SUMS), tar шифруется здесь (AES-256-CBC, ключ из PBKDF2 по
# ключу-файлу), на Диск уходит только шифротекст. Токен — в файле заголовка
# (права 600), не в командной строке. Причина ошибки — в stdout.
yadisk_api() {
  # yadisk_api МЕТОД ПУТЬ [аргументы curl…] — запрос к API, тело ответа в stdout.
  local method="$1" path="$2"
  shift 2
  curl -s --max-time 60 -H @"$YADISK_HEADER" -X "$method" -G "https://cloud-api.yandex.net/v1/disk/resources$path" "$@"
}

yadisk_copy() {
  local keep key work name archive size link href code remote cutoff old f
  # shellcheck disable=SC1090
  . "$YADISK_ENV"
  key="${YADISK_KEY_FILE:-$HOME/.config/legalai/backup.key}"
  YADISK_HEADER="${YADISK_HEADER:-$HOME/.config/legalai/yadisk.header}"
  keep="${YADISK_KEEP_DAYS:-60}"
  if [ ! -r "$key" ] || [ ! -r "$YADISK_HEADER" ]; then
    echo "нет ключа шифрования или токена Диска — запустите setup_yadisk_backup.sh"
    return 1
  fi
  work="$(mktemp -d)"
  name="legal_ai_$TIMESTAMP"
  archive="$work/$name.tar.enc"
  mkdir "$work/$name"
  for f in "$@"; do
    [ -n "$f" ] && cp "$f" "$work/$name/"
  done
  (cd "$work/$name" && shasum -a 256 -- * > SHA256SUMS)
  if ! tar -C "$work" -cf - "$name" \
    | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 -salt -pass "file:$key" -out "$archive"; then
    rm -rf "$work"
    echo "не удалось зашифровать архив"
    return 1
  fi
  size="$(stat -f %z "$archive")"
  # Ссылка на загрузку, затем сам файл — по ссылке, без токена.
  link="$(yadisk_api GET /upload --data-urlencode "path=app:/$name.tar.enc" --data-urlencode "overwrite=true")"
  href="$(printf '%s' "$link" | sed -n 's/.*"href":"\([^"]*\)".*/\1/p')"
  if [ -z "$href" ]; then
    rm -rf "$work"
    case "$link" in
      *UnauthorizedError*) echo "Яндекс Диск не принял токен — выпустите новый (срок жизни — год)" ;;
      *InsufficientStorage*) echo "на Яндекс Диске закончилось место" ;;
      *) echo "Яндекс Диск не дал ссылку на загрузку: $(printf '%s' "$link" | head -c 200)" ;;
    esac
    return 1
  fi
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 900 -T "$archive" "$href")"
  rm -rf "$work"
  case "$code" in
    201 | 202) ;;
    507) echo "на Яндекс Диске закончилось место (507)"; return 1 ;;
    *) echo "Яндекс Диск не принял копию (ответ ${code:-нет})"; return 1 ;;
  esac
  remote="$(yadisk_api GET "" --data-urlencode "path=app:/$name.tar.enc" --data-urlencode "fields=size" \
    | grep -o '"size":[0-9]*' | grep -o '[0-9]*$' | head -1)"
  if [ "$remote" != "$size" ]; then
    echo "размер копии на Диске (${remote:-нет}) не совпал с архивом ($size)"
    return 1
  fi
  # Старые копии — по дате в имени: legal_ai_ГГГГММДД_ччммсс.tar.enc.
  cutoff="$(date -v-"${keep}"d +%Y%m%d)"
  for old in $(yadisk_api GET "" --data-urlencode "path=app:/" --data-urlencode "limit=1000" \
    --data-urlencode "fields=_embedded.items.name" \
    | grep -o 'legal_ai_[0-9]\{8\}_[0-9]\{6\}\.tar\.enc' | sort -u); do
    if [ "${old:9:8}" \< "$cutoff" ]; then
      yadisk_api DELETE "" --data-urlencode "path=app:/$old" --data-urlencode "permanently=true" >/dev/null || true
    fi
  done
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

problems=""
add_problem() { problems="${problems:+$problems; }$1"; }

BOT_TARGET="$BACKUP_DIR/legal_ai_bot_$TIMESTAMP.db"
if bot_error="$(bot_db_copy "$BOT_TARGET")"; then
  echo "Bot DB copied: $(basename "$BOT_TARGET") ($(du -h "$BOT_TARGET" | cut -f1))"
else
  echo "Bot DB copy FAILED: $bot_error" >&2
  add_problem "копия базы бота не удалась: $bot_error"
  BOT_TARGET=""
fi
find "$BACKUP_DIR" -name 'legal_ai_bot_*.db' -mtime +"$BACKUP_KEEP_DAYS" -delete

if [ -r "$NAS_ENV" ]; then
  if nas_error="$(nas_copy "$TARGET")"; then
    echo "NAS copy completed"
  else
    echo "NAS copy FAILED: $nas_error" >&2
    add_problem "копия на NAS не удалась: $nas_error"
  fi
fi

if [ -r "$YADISK_ENV" ]; then
  if yadisk_error="$(yadisk_copy "$TARGET" "$BOT_TARGET")"; then
    echo "Yandex Disk copy completed"
  else
    echo "Yandex Disk copy FAILED: $yadisk_error" >&2
    add_problem "копия на Яндекс Диск не удалась: $yadisk_error"
  fi
fi

if [ -z "$problems" ]; then
  record_health true "" 1
else
  record_health false "$problems" 1
  exit 1
fi
