#!/bin/bash
set -euo pipefail

DUMP_FILE=${1:-}
if [ -z "$DUMP_FILE" ]; then
  echo "Usage: $0 <dump_file>"
  exit 1
fi

CONTAINER=${POSTGRES_CONTAINER:-legal-ai-postgres}
PGUSER=${PGUSER:-legalai}
PGDB=${PGDB:-legalai}

docker exec -i "$CONTAINER" pg_restore -U "$PGUSER" -d "$PGDB" --clean --if-exists < "$DUMP_FILE"
echo "Restore completed from: $DUMP_FILE"
