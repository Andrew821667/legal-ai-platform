#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/Users/legalai/projects/legal-ai-platform}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/compose/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
NEWS_PROXY_LABEL="ru.legalai.news-source-proxy"
NEWS_PROXY_SCRIPT="/Users/andrej/app-vpn/restricted_connect_proxy.py"
NEWS_PROXY_PLIST="/Users/andrej/Library/LaunchAgents/${NEWS_PROXY_LABEL}.plist"
NEWS_RSS_PROXY_URL="http://192.168.64.1:18081"

: "${GHCR_USERNAME:?GHCR_USERNAME is required}"
: "${GHCR_TOKEN:?GHCR_TOKEN is required}"
: "${WEB_IMAGE:?WEB_IMAGE is required}"
: "${LEAD_BOT_IMAGE:?LEAD_BOT_IMAGE is required}"
: "${NEWS_IMAGE:?NEWS_IMAGE is required}"

services=(web lead-bot assistant-api news-generate news-admin-bot)
containers=(
  legal-ai-web
  legal-ai-lead-bot
  legal-ai-assistant-api
  legal-ai-news-generate
  legal-ai-news-admin-bot
)
images=(
  "$WEB_IMAGE"
  "$LEAD_BOT_IMAGE"
  "$LEAD_BOT_IMAGE"
  "$NEWS_IMAGE"
  "$NEWS_IMAGE"
)

cd "$APP_DIR"

msk_time="$(TZ=Europe/Moscow date '+%H:%M')"
case "$msk_time" in
  07:5[0-9]|08:[0-3][0-9]|08:40|16:5[0-9]|17:[0-3][0-9]|17:40)
    echo "ERROR: editorial deploy is blocked near a scheduled news-generation slot ($msk_time MSK)"
    exit 1
    ;;
esac

install -m 0755 -o andrej -g staff \
  infra/scripts/restricted_connect_proxy.py "$NEWS_PROXY_SCRIPT"
install -m 0644 -o andrej -g staff \
  "infra/launchd/${NEWS_PROXY_LABEL}.plist" "$NEWS_PROXY_PLIST"

launchctl bootout "gui/501/${NEWS_PROXY_LABEL}" 2>/dev/null || true
launchctl bootstrap gui/501 "$NEWS_PROXY_PLIST"
launchctl kickstart -k "gui/501/${NEWS_PROXY_LABEL}"

if ! grep -qxF "NEWS_RSS_PROXY_URL=$NEWS_RSS_PROXY_URL" "$ENV_FILE"; then
  cp -p "$ENV_FILE" "${ENV_FILE}.bak.$(date '+%Y%m%d%H%M%S')"
  env_tmp="$(mktemp)"
  awk -v value="$NEWS_RSS_PROXY_URL" '
    BEGIN { replaced = 0 }
    /^NEWS_RSS_PROXY_URL=/ {
      if (!replaced) print "NEWS_RSS_PROXY_URL=" value
      replaced = 1
      next
    }
    { print }
    END { if (!replaced) print "NEWS_RSS_PROXY_URL=" value }
  ' "$ENV_FILE" > "$env_tmp"
  install -m 0600 -o legalai -g staff "$env_tmp" "$ENV_FILE"
  rm -f "$env_tmp"
fi

for _ in $(seq 1 20); do
  if curl -fsSI --max-time 15 --proxy "$NEWS_RSS_PROXY_URL" \
    'https://news.google.com/rss?hl=ru&gl=RU&ceid=RU:ru' >/dev/null; then
    break
  fi
  sleep 1
done
curl -fsSI --max-time 15 --proxy "$NEWS_RSS_PROXY_URL" \
  'https://news.google.com/rss?hl=ru&gl=RU&ceid=RU:ru' >/dev/null

docker_config="$(mktemp -d)"
before="$(mktemp)"
trap 'rm -rf "$docker_config" "$before"' EXIT

docker_source_dir="${DOCKER_CONFIG:-$HOME/.docker}"
docker_source_config="$docker_source_dir/config.json"
docker_auth="$(printf '%s:%s' "$GHCR_USERNAME" "$GHCR_TOKEN" | base64 | tr -d '\n')"

if [ -d "$docker_source_dir/contexts" ]; then
  cp -R "$docker_source_dir/contexts" "$docker_config/contexts"
fi

if command -v jq >/dev/null 2>&1 && [ -f "$docker_source_config" ]; then
  jq --arg auth "$docker_auth" '
    del(.credsStore, .credHelpers)
    | .auths = (.auths // {})
    | .auths["ghcr.io"] = {"auth": $auth}
  ' "$docker_source_config" > "$docker_config/config.json"
else
  docker_context="$(docker context show 2>/dev/null || true)"
  {
    printf '{\n'
    printf '  "auths": {"ghcr.io": {"auth": "%s"}}' "$docker_auth"
    if [ -n "$docker_context" ]; then
      printf ',\n  "currentContext": "%s"' "$docker_context"
    fi
    printf '\n}\n'
  } > "$docker_config/config.json"
fi
export DOCKER_CONFIG="$docker_config"

compose=(docker compose -p compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

docker ps -a --format '{{.Names}} {{.ID}} {{.State}}' | sort > "$before"
deploy_started="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

echo "Pulling editorial images..."
"${compose[@]}" pull "${services[@]}"

echo "Replacing editorial services..."
"${compose[@]}" up -d --no-build --no-deps "${services[@]}"

is_target() {
  local name="$1"
  local target
  for target in "${containers[@]}"; do
    [ "$name" = "$target" ] && return 0
  done
  return 1
}

echo "Checking untouched containers..."
while read -r name old_id old_state; do
  is_target "$name" && continue
  current="$(docker ps -a --filter "name=^/${name}$" --format '{{.ID}} {{.State}}')"
  if [ "$current" != "$old_id $old_state" ]; then
    echo "ERROR: unrelated container changed: $name ($old_id $old_state -> ${current:-missing})"
    exit 1
  fi
done < "$before"

wait_for_container() {
  local name="$1"
  local state
  for _ in $(seq 1 60); do
    state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$name" 2>/dev/null || true)"
    if [ "$state" = "healthy" ] || [ "$state" = "running" ]; then
      return 0
    fi
    sleep 2
  done
  echo "ERROR: $name did not become ready"
  docker logs --tail=100 "$name" 2>&1 || true
  return 1
}

echo "Waiting for editorial services..."
for name in "${containers[@]}"; do
  wait_for_container "$name"
done

for idx in "${!containers[@]}"; do
  name="${containers[$idx]}"
  expected="${images[$idx]}"
  actual="$(docker inspect -f '{{.Config.Image}}' "$name")"
  if [ "$actual" != "$expected" ]; then
    echo "ERROR: $name uses $actual instead of $expected"
    exit 1
  fi
done

curl -fsS https://ai-verdict.ru/ >/dev/null
curl -fsS https://ai-verdict.ru/services >/dev/null
curl -fsS https://ai-verdict.ru/miniapp >/dev/null
docker exec legal-ai-assistant-api python -c \
  "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=8).status == 200"
docker exec legal-ai-lead-bot python -c '
import urllib.error
import urllib.request

try:
    urllib.request.urlopen("https://api.telegram.org", timeout=8)
except urllib.error.HTTPError:
    pass
'

for name in "${containers[@]}"; do
  logs="$(docker logs --since "$deploy_started" --tail=200 "$name" 2>&1 || true)"
  if printf '%s\n' "$logs" | grep -Eqi \
    'NameResolutionError|Connection refused|Unauthorized|Conflict: terminated by other getUpdates request|Network is unreachable|Traceback|ERROR'; then
    echo "ERROR: critical startup pattern in $name"
    printf '%s\n' "$logs"
    exit 1
  fi
done


if docker logs --since "$deploy_started" legal-ai-news-generate 2>&1 \
  | grep -q 'generate_loop_slot_triggered'; then
  echo "ERROR: news generation started during the editorial deploy"
  exit 1
fi

docker ps --format '{{.Names}} {{.Image}} {{.Status}}' \
  | grep -E '^legal-ai-(web|lead-bot|assistant-api|news-generate|news-admin-bot) '
echo "Editorial deploy complete"
