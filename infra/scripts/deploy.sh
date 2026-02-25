#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose -f infra/compose/docker-compose.prod.yml"

if [ -n "${1:-}" ]; then
  git pull origin "$1"
else
  git pull origin main
fi

echo "Waiting for Postgres..."
until $COMPOSE exec -T postgres pg_isready -U "${POSTGRES_USER:-legalai}" -d "${POSTGRES_DB:-legalai}" -q; do
  sleep 1
done

echo "Postgres ready"
$COMPOSE run --rm core-api bash -lc "cd /app/apps/core-api && alembic upgrade head"
$COMPOSE run --rm core-api python -m core_api.cli create-admin-key --name "deploy-admin" --if-no-keys

$COMPOSE pull
$COMPOSE up -d --no-deps core-api
$COMPOSE up -d --no-deps lead-bot || true

sleep 5
curl -sf http://localhost:8000/health >/dev/null
echo "Deploy complete"
