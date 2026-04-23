#!/usr/bin/env bash
set -euo pipefail

PUBLIC_APP_DIR="${PUBLIC_APP_DIR:-/Users/legalai/projects/legal-ai-platform}"
BOT_APP_DIR="${BOT_APP_DIR:-/Users/aiwork/legal-ai-platform}"
PUBLIC_COMPOSE="${PUBLIC_COMPOSE:-infra/compose/docker-compose.public.yml}"
BOT_COMPOSE="${BOT_COMPOSE:-docker-compose.bots.yml}"
PUBLIC_ENV="${PUBLIC_ENV:-.env}"
BOT_ENV="${BOT_ENV:-.env}"
CORE_API_HEALTH_URL="${CORE_API_HEALTH_URL:-http://127.0.0.1:${CORE_API_PUBLISH_PORT:-8100}}"
SKIP_PULL="${SKIP_PULL:-0}"

public_compose=(docker compose -p compose --env-file "$PUBLIC_ENV" -f "$PUBLIC_COMPOSE")
bot_compose=(docker compose --env-file "$BOT_ENV" -f "$BOT_COMPOSE")

if [ -n "${GHCR_USERNAME:-}" ] && [ -n "${GHCR_TOKEN:-}" ]; then
  echo "Logging in to GHCR..."
  printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
fi

cd "$PUBLIC_APP_DIR"

if [ "$SKIP_PULL" != "1" ]; then
  echo "Pulling public images where available..."
  "${public_compose[@]}" pull postgres core-api web caddy || true
fi

echo "Starting public contour..."
"${public_compose[@]}" up -d --no-build --force-recreate postgres core-api web caddy

echo "Waiting for Core API..."
for _ in $(seq 1 60); do
  if curl -fsS "${CORE_API_HEALTH_URL%/}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "${CORE_API_HEALTH_URL%/}/health" >/dev/null

cd "$BOT_APP_DIR"

if [ "$SKIP_PULL" != "1" ]; then
  echo "Pulling bot/news images where available..."
  "${bot_compose[@]}" pull lead-bot news-generate news-telegram-ingest news-publish news-admin-bot news-reader-bot news-reader-digest || true
fi

echo "Starting Telegram/VPN contour..."
"${bot_compose[@]}" up -d --no-build --force-recreate \
  lead-bot \
  news-admin-bot \
  news-generate \
  news-telegram-ingest \
  news-publish \
  news-reader-bot \
  news-reader-digest

echo "Mac Mini deploy complete"
