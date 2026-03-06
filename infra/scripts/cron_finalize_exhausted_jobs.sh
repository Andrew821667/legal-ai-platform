#!/bin/bash
set -euo pipefail

CORE_API_URL=${CORE_API_URL:-http://localhost:8000}
LIMIT=${CONTRACT_FINALIZE_EXHAUSTED_LIMIT:-200}

curl -sf -X POST "$CORE_API_URL/api/v1/contract-jobs/finalize-exhausted-new?limit=${LIMIT}" \
  -H "X-API-Key: ${API_KEY_ADMIN:?API_KEY_ADMIN is required}" >/dev/null
