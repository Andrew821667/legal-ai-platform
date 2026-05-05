#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required to run core-api tests with Postgres"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: docker daemon is not reachable. Start Docker Desktop and retry."
  exit 1
fi

CONTAINER="${CORE_API_TEST_POSTGRES_CONTAINER:-legal-ai-core-api-test-postgres-$$}"
POSTGRES_IMAGE="${CORE_API_TEST_POSTGRES_IMAGE:-postgres:16-alpine}"
POSTGRES_USER="${CORE_API_TEST_POSTGRES_USER:-legalai_app}"
POSTGRES_PASSWORD="${CORE_API_TEST_POSTGRES_PASSWORD:-change_me_local_only}"
POSTGRES_DB="${CORE_API_TEST_POSTGRES_DB:-legalai_platform}"
POSTGRES_PORT=""

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[1/3] Starting temporary Postgres (${POSTGRES_IMAGE})..."
docker run -d \
  --name "$CONTAINER" \
  -e POSTGRES_USER="$POSTGRES_USER" \
  -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  -e POSTGRES_DB="$POSTGRES_DB" \
  -p 127.0.0.1::5432 \
  "$POSTGRES_IMAGE" >/dev/null

POSTGRES_PORT="$(docker port "$CONTAINER" 5432/tcp | sed 's/.*://')"
if [ -z "$POSTGRES_PORT" ]; then
  echo "ERROR: unable to resolve temporary Postgres port"
  exit 1
fi

echo "[2/3] Waiting for Postgres readiness..."
deadline=$((SECONDS + ${CORE_API_TEST_POSTGRES_TIMEOUT_SECONDS:-60}))
until docker exec "$CONTAINER" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "ERROR: temporary Postgres did not become ready in time"
    docker logs "$CONTAINER" || true
    exit 1
  fi
  sleep 1
done

echo "[3/3] Running core-api tests..."
DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}" \
  uv run pytest apps/core-api/tests/ "$@"
