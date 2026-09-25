#!/usr/bin/env bash
# Проверочное восстановление: поднимается ли база из бэкапа.
#
# Бэкап, который ни разу не восстанавливали, — надежда, а не бэкап. Скрипт
# берёт дамп (по умолчанию — самый свежий в BACKUP_DIR), восстанавливает его во
# ВРЕМЕННЫЙ контейнер Postgres без портов наружу и сверяет число строк в
# ключевых таблицах с живой базой. Живую базу только читает. Временный
# контейнер удаляется в любом случае.
#
# FRESH_DUMP=1 — сначала снять свежий дамп (backup_postgres.sh), потом его же
# восстановить: так сверка с живой базой точная.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/legal-ai}"
LIVE="${POSTGRES_CONTAINER:-legal-ai-postgres}"
PGUSER="${PGUSER:-legalai_app}"
PGDB="${PGDB:-legalai_platform}"
DRILL="legal-ai-restore-drill-$$"
TABLES="leads legal_intakes nda_signatures service_agreements work_acts telegram_deliveries audit_log"

if [ "${FRESH_DUMP:-0}" = "1" ]; then
  BACKUP_DIR="$BACKUP_DIR" "$ROOT_DIR/infra/scripts/backup_postgres.sh"
fi

DUMP="${1:-$(ls -t "$BACKUP_DIR"/*.dump 2>/dev/null | head -1 || true)}"
if [ -z "$DUMP" ] || [ ! -s "$DUMP" ]; then
  echo "FAIL: дамп не найден в $BACKUP_DIR"
  exit 1
fi
echo "Дамп: $DUMP ($(du -h "$DUMP" | cut -f1), $(date -r "$DUMP" '+%d.%m.%Y %H:%M'))"

cleanup() { docker rm -f "$DRILL" >/dev/null 2>&1 || true; }
trap cleanup EXIT

IMAGE="$(docker inspect -f '{{.Config.Image}}' "$LIVE")"
docker run -d --name "$DRILL" -e POSTGRES_USER="$PGUSER" -e POSTGRES_PASSWORD=drill -e POSTGRES_DB="$PGDB" "$IMAGE" >/dev/null
for _ in $(seq 1 60); do
  docker exec "$DRILL" pg_isready -U "$PGUSER" -d "$PGDB" -q && break
  sleep 1
done

started=$(date +%s)
if ! docker exec -i "$DRILL" pg_restore -U "$PGUSER" -d "$PGDB" --no-owner --no-privileges --exit-on-error < "$DUMP"; then
  echo "FAIL: pg_restore не смог восстановить дамп"
  exit 1
fi
echo "Восстановлено за $(( $(date +%s) - started )) с"

count() {
  docker exec "$1" psql -U "$PGUSER" -d "$PGDB" -Atc "select count(*) from $2" 2>/dev/null || echo "нет"
}

status=0
printf "%-22s %10s %10s\n" "таблица" "в бэкапе" "в живой"
for table in $TABLES; do
  restored="$(count "$DRILL" "$table")"
  live="$(count "$LIVE" "$table")"
  printf "%-22s %10s %10s\n" "$table" "$restored" "$live"
  if [ "$restored" = "нет" ]; then
    status=1
  fi
done
restored_version="$(docker exec "$DRILL" psql -U "$PGUSER" -d "$PGDB" -Atc "select version_num from alembic_version")"
live_version="$(docker exec "$LIVE" psql -U "$PGUSER" -d "$PGDB" -Atc "select version_num from alembic_version")"
echo "Версия схемы: в бэкапе $restored_version, в живой $live_version"

if [ "$status" -ne 0 ]; then
  echo "FAIL: в восстановленной базе нет части таблиц"
  exit 1
fi
echo "OK: бэкап восстанавливается"
