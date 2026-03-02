#!/bin/bash
set -euo pipefail

CORE_API_URL=${CORE_API_URL:-http://localhost:8000}
API_KEY=${API_KEY_ADMIN:?API_KEY_ADMIN is required}

curl -sf -X POST "$CORE_API_URL/api/v1/scheduled-posts/reset-stale?older_than_minutes=30" \
  -H "X-API-Key: $API_KEY" >/dev/null
