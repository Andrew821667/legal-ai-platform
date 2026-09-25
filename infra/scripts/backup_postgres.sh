#!/bin/bash
# Дамп базы в формате pg_dump -Fc. Хранит BACKUP_KEEP_DAYS дней.
#
# Запускается ежедневно launchd-агентом (infra/launchd/ru.legalai.postgres-backup.plist)
# и вручную перед рискованными изменениями. Проверить, что дамп
# восстанавливается, — infra/scripts/restore_drill.sh.
#
# Паспортные данные в дампе — шифротекст; ключ (PII_ENCRYPTION_KEY) хранится
# отдельно от бэкапов: ключ рядом с дампом = дамп открытым текстом.
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=${BACKUP_DIR:-$HOME/backups/legal-ai}
BACKUP_KEEP_DAYS=${BACKUP_KEEP_DAYS:-14}
mkdir -p "$BACKUP_DIR"
CONTAINER=${POSTGRES_CONTAINER:-legal-ai-postgres}
PGUSER=${PGUSER:-legalai_app}
PGDB=${PGDB:-legalai_platform}
TARGET="$BACKUP_DIR/legal_ai_$TIMESTAMP.dump"

# Во временный файл: оборванный дамп не должен выглядеть как свежий бэкап.
docker exec "$CONTAINER" pg_dump -U "$PGUSER" -Fc "$PGDB" > "$TARGET.part"
if [ ! -s "$TARGET.part" ]; then
  rm -f "$TARGET.part"
  echo "Backup FAILED: empty dump" >&2
  exit 1
fi
mv "$TARGET.part" "$TARGET"
chmod 600 "$TARGET"
find "$BACKUP_DIR" -name 'legal_ai_*.dump' -mtime +"$BACKUP_KEEP_DAYS" -delete
echo "Backup completed: $(basename "$TARGET") ($(du -h "$TARGET" | cut -f1))"
