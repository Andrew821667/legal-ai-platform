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

echo "Pulling latest images..."
$COMPOSE pull postgres caddy core-api lead-bot || true

echo "Ensuring Postgres is running..."
$COMPOSE up -d postgres

echo "Waiting for Postgres..."
until $COMPOSE exec -T postgres pg_isready -U "${POSTGRES_USER:-legalai}" -d "${POSTGRES_DB:-legalai}" -q; do
  sleep 1
done

echo "Postgres ready"

echo "Running database migrations with fresh core-api image..."
$COMPOSE run --rm core-api bash -lc "cd /app/apps/core-api && alembic upgrade head"
$COMPOSE run --rm core-api python -m core_api.cli create-admin-key --name "deploy-admin" --if-no-keys

$COMPOSE up -d --no-deps core-api
$COMPOSE up -d --no-deps lead-bot || true
$COMPOSE up -d --build --no-deps web || true
$COMPOSE up -d --build --no-deps news-generate || true
$COMPOSE up -d --build --no-deps news-telegram-ingest || true
$COMPOSE up -d --build --no-deps news-publish || true
$COMPOSE up -d --build --no-deps news-admin-bot || true
$COMPOSE up -d --build --no-deps news-reader-bot || true
$COMPOSE up -d --no-deps caddy || true

sleep 5
curl -sf http://localhost:8000/health >/dev/null
echo "Deploy complete"
