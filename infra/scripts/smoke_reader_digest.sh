#!/usr/bin/env bash
set -euo pipefail

CORE_API_URL="${CORE_API_URL:-http://localhost:8000}"
API_KEY_ADMIN="${API_KEY_ADMIN:-}"

if [[ -z "${API_KEY_ADMIN}" ]]; then
  echo "ERROR: API_KEY_ADMIN is required"
  exit 1
fi

echo "[1/3] Check automation control key news.reader_digest.enabled"
controls_json="$(curl -fsS -H "X-API-Key: ${API_KEY_ADMIN}" "${CORE_API_URL}/api/v1/automation-controls?scope=news")"
if ! grep -q '"key":"news.reader_digest.enabled"' <<<"${controls_json}"; then
  echo "ERROR: news.reader_digest.enabled not found"
  exit 1
fi
echo "OK: control key found"

echo "[2/3] Check workers/status contains news-reader-digest"
workers_json="$(curl -fsS -H "X-API-Key: ${API_KEY_ADMIN}" "${CORE_API_URL}/api/v1/workers/status")"
if ! grep -q '"worker_id":"news-reader-digest"' <<<"${workers_json}"; then
  echo "ERROR: news-reader-digest worker not found in workers/status"
  exit 1
fi
echo "OK: worker is registered"

echo "[3/3] Check worker activity endpoint"
curl -fsS -H "X-API-Key: ${API_KEY_ADMIN}" "${CORE_API_URL}/api/v1/workers/news-reader-digest/activity?hours=24&limit=10" >/dev/null
echo "OK: worker activity endpoint is reachable"

echo "Smoke check for reader-digest: PASSED"
