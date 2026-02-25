#!/bin/bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=${BACKUP_DIR:-/var/backups/legal-ai}
mkdir -p "$BACKUP_DIR"

CONTAINER=${POSTGRES_CONTAINER:-legal-ai-postgres}
PGUSER=${PGUSER:-legalai}
PGDB=${PGDB:-legalai}

docker exec "$CONTAINER" pg_dump -U "$PGUSER" -Fc "$PGDB" > "$BACKUP_DIR/legal_ai_$TIMESTAMP.dump"
find "$BACKUP_DIR" -name '*.dump' -mtime +7 -delete

echo "Backup completed: legal_ai_$TIMESTAMP.dump"
