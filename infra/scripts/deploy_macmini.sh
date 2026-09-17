#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-${PUBLIC_APP_DIR:-/Users/legalai/projects/legal-ai-platform}}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/compose/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
CORE_API_HEALTH_URL="${CORE_API_HEALTH_URL:-http://127.0.0.1:${CORE_API_PUBLISH_PORT:-8000}}"
SKIP_PULL="${SKIP_PULL:-0}"
SKIP_PRUNE="${SKIP_PRUNE:-0}"
COMPOSE_BUILD_MODE="${COMPOSE_BUILD_MODE:-}"
FORCE_RECREATE="${FORCE_RECREATE:-0}"

services=(
  postgres
  core-api
  web
  lead-bot
  news-generate
  news-telegram-ingest
  news-publish
  news-admin-bot
  news-reader-bot
  news-reader-digest
  caddy
)

if [ -n "${GHCR_USERNAME:-}" ] && [ -n "${GHCR_TOKEN:-}" ]; then
  docker_config_cleanup="$(mktemp -d)"
  docker_source_dir="${DOCKER_CONFIG:-$HOME/.docker}"
  docker_source_config="$docker_source_dir/config.json"
  docker_auth="$(printf '%s:%s' "$GHCR_USERNAME" "$GHCR_TOKEN" | base64 | tr -d '\n')"

  if [ -d "$docker_source_dir/contexts" ]; then
    cp -R "$docker_source_dir/contexts" "$docker_config_cleanup/contexts"
  fi

  if command -v jq >/dev/null 2>&1 && [ -f "$docker_source_config" ]; then
    jq --arg auth "$docker_auth" '
      del(.credsStore, .credHelpers)
      | .auths = (.auths // {})
      | .auths["ghcr.io"] = {"auth": $auth}
    ' "$docker_source_config" > "$docker_config_cleanup/config.json"
  else
    docker_context="$(docker context show 2>/dev/null || true)"
    {
      printf '{\n'
      printf '  "auths": {"ghcr.io": {"auth": "%s"}}' "$docker_auth"
      if [ -n "$docker_context" ]; then
        printf ',\n  "currentContext": "%s"' "$docker_context"
      fi
      printf '\n}\n'
    } > "$docker_config_cleanup/config.json"
  fi

  export DOCKER_CONFIG="$docker_config_cleanup"
  trap 'rm -rf "$docker_config_cleanup"' EXIT

  echo "Configured GHCR credentials for this deploy."
fi

cd "$APP_DIR"

# Миграция 0032 шифрует паспортные данные ключом из .env и без ключа
# останавливается — а вместе с ней и запуск core-api (alembic идёт перед
# uvicorn). Проверяем до того, как трогать контейнеры: не начать деплой
# лучше, чем уронить ядро. Проверяется и формат: ключ Fernet — это ровно
# 44 знака base64url с «=» на конце, а в поле уже однажды попадала не та
# строка из буфера обмена. Как завести ключ — docs/runbook.md,
# «Шифрование паспортных данных».
if ! grep -Eq '^PII_ENCRYPTION_KEY=[A-Za-z0-9_-]{43}=$' "$ENV_FILE"; then
  echo "PII_ENCRYPTION_KEY в $ENV_FILE не задан или не похож на ключ Fernet (44 знака base64url) — деплой остановлен до того, как что-то пересоздано." >&2
  exit 1
fi

compose=(docker compose -p compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

if [ -z "$COMPOSE_BUILD_MODE" ]; then
  if [ -n "${CORE_API_IMAGE:-}" ] || [ -n "${WEB_IMAGE:-}" ] || [ -n "${LEAD_BOT_IMAGE:-}" ] || [ -n "${NEWS_IMAGE:-}" ] || [ -n "${NEWS_READER_IMAGE:-}" ] || [ -n "${CADDY_IMAGE:-}" ]; then
    COMPOSE_BUILD_MODE="--no-build"
  else
    COMPOSE_BUILD_MODE="--build"
  fi
fi

# Старые образы — до pull, а не после: каждый деплой тянет шесть новых, и
# за день без чистки виртуальный диск Docker Desktop переполнился — слои
# перестали распаковываться, web и мини-апп клиентов упали в 500. Удаляются
# только образы, которые не использует ни один контейнер; тома не трогаются.
# SKIP_PRUNE=1 — для ручного деплоя, когда образы уже собраны локально этим же
# запуском (docker build) и ещё не привязаны ни к одному контейнеру: без этого
# prune стирает их же раньше, чем до них доходит `compose up`.
if [ "$SKIP_PRUNE" != "1" ]; then
  echo "Pruning unused images and build cache..."
  docker image prune -af >/dev/null 2>&1 || echo "image prune failed; continuing"
  docker builder prune -af >/dev/null 2>&1 || echo "builder prune failed; continuing"
fi

if [ "$SKIP_PULL" != "1" ]; then
  echo "Pulling production images where available..."
  "${compose[@]}" pull "${services[@]}" || true
fi

recreate_args=()
if [ "$FORCE_RECREATE" = "1" ]; then
  recreate_args=(--force-recreate)
fi

echo "Starting production stack..."
"${compose[@]}" up -d "$COMPOSE_BUILD_MODE" postgres
if [ "${#recreate_args[@]}" -gt 0 ]; then
  "${compose[@]}" up -d "$COMPOSE_BUILD_MODE" "${recreate_args[@]}" \
    core-api \
    web \
    lead-bot \
    news-generate \
    news-telegram-ingest \
    news-publish \
    news-admin-bot \
    news-reader-bot \
    news-reader-digest \
    caddy
else
  "${compose[@]}" up -d "$COMPOSE_BUILD_MODE" \
    core-api \
    web \
    lead-bot \
    news-generate \
    news-telegram-ingest \
    news-publish \
    news-admin-bot \
    news-reader-bot \
    news-reader-digest \
    caddy
fi

echo "Waiting for Core API..."
for _ in $(seq 1 60); do
  if curl -fsS "${CORE_API_HEALTH_URL%/}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "${CORE_API_HEALTH_URL%/}/health" >/dev/null

if [ -x "$APP_DIR/infra/scripts/macmini_deploy_check.sh" ]; then
  COMPOSE_PROJECT=compose COMPOSE_FILE="$COMPOSE_FILE" "$APP_DIR/infra/scripts/macmini_deploy_check.sh"
fi

if [ -x "$APP_DIR/infra/scripts/submit_indexnow.sh" ]; then
  "$APP_DIR/infra/scripts/submit_indexnow.sh" || echo "IndexNow notification failed; deploy remains healthy."
fi

echo "Mac Mini deploy complete"
