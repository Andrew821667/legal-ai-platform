#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

env_value() {
  local key="$1"
  if [ ! -f ".env" ]; then
    return 0
  fi
  awk -F= -v key="$key" '
    $1 == key {
      sub(/^[^=]*=/, "")
      gsub(/^[[:space:]]+|[[:space:]]+$/, "")
      gsub(/^"|"$/, "")
      gsub(/^'\''|'\''$/, "")
      print
      exit
    }
  ' .env
}

DOMAIN="${DOMAIN:-$(env_value DOMAIN)}"
DOMAIN="${DOMAIN:-ai-verdict.ru}"
CORE_API_HOST_URL="${CORE_API_HOST_URL:-$(env_value CORE_API_HOST_URL)}"
CORE_API_PUBLISH_PORT="${CORE_API_PUBLISH_PORT:-$(env_value CORE_API_PUBLISH_PORT)}"
CORE_API_HEALTH_URL="${CORE_API_HEALTH_URL:-${CORE_API_HOST_URL:-http://localhost:${CORE_API_PUBLISH_PORT:-8000}}}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/compose/docker-compose.prod.yml}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-}"

if [ -n "$COMPOSE_PROJECT" ]; then
  COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE")
else
  COMPOSE=(docker compose -f "$COMPOSE_FILE")
fi

echo "[1/6] DNSSEC DS at .ru registry"
if command -v dig >/dev/null 2>&1; then
  ds_records="$(dig +short "$DOMAIN" DS @a.dns.ripn.net 2>/dev/null || true)"
  if [ -n "$ds_records" ]; then
    echo "WARN: DS record still exists for $DOMAIN; Cloudflare zone can stay pending until registrar removes it."
  else
    echo "OK: no DS record at .ru registry"
  fi
else
  echo "SKIP: dig is not installed"
fi

echo "[2/6] Public DNS resolution"
if command -v dig >/dev/null 2>&1; then
  dig +short "$DOMAIN" A @1.1.1.1 || true
  dig +short "www.$DOMAIN" CNAME @1.1.1.1 || true
else
  echo "SKIP: dig is not installed"
fi

echo "[3/6] core-api external health: ${CORE_API_HEALTH_URL}/health"
curl -fsS "${CORE_API_HEALTH_URL%/}/health" >/dev/null
echo "OK: core-api health is reachable"

echo "[4/6] Compose service status"
"${COMPOSE[@]}" ps

echo "[5/6] Docker network aliases for core-api"
core_container="$("${COMPOSE[@]}" ps -q core-api || true)"
if [ -z "$core_container" ]; then
  core_container="$(docker ps -q --filter name='^/legal-ai-core-api$' || true)"
fi
if [ -n "$core_container" ]; then
  docker inspect "$core_container" \
    --format '{{range $name, $net := .NetworkSettings.Networks}}{{println $name}}{{printf "Aliases: %v\n" $net.Aliases}}{{printf "DNSNames: %v\n" $net.DNSNames}}{{end}}'
else
  echo "WARN: core-api container was not found through $COMPOSE_FILE or by name legal-ai-core-api"
fi

echo "[6/6] Recent critical bot/core logs"
"${COMPOSE[@]}" logs --since "${LOG_SINCE:-10m}" --tail=300 core-api lead-bot news-admin-bot news-generate news-telegram-ingest news-publish news-reader-bot news-reader-digest 2>/dev/null \
  | grep -Eai "NameResolutionError|Connection refused|Unauthorized|Conflict: terminated by other getUpdates request|Network is unreachable|Traceback|ERROR" \
  || echo "OK: no critical patterns found in recent logs"

echo "Mac Mini deploy check complete"
