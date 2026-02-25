#!/bin/bash
set -euo pipefail

CORE_API_URL=${CORE_API_URL:-http://localhost:8000}

curl -sf -X POST "$CORE_API_URL/api/v1/contract-jobs/reset-stale?older_than_minutes=30" \
  -H "X-API-Key: ${API_KEY_ADMIN:?API_KEY_ADMIN is required}" >/dev/null
