#!/bin/bash
set -euo pipefail

CORE_API_URL=${CORE_API_URL:-http://localhost:8000}
LIMIT_EACH=${CONTRACT_MAINTENANCE_LIMIT_EACH:-200}
STALE_MINUTES=${CONTRACT_MAINTENANCE_STALE_MINUTES:-30}
RETRY_FAILED_ENABLED=${CONTRACT_MAINTENANCE_RETRY_FAILED:-0}
RETRY_FAILED_ONLY_RETRYABLE=${CONTRACT_MAINTENANCE_RETRY_FAILED_ONLY_RETRYABLE:-1}
RETRY_FAILED_OLDER_THAN_MINUTES=${CONTRACT_MAINTENANCE_RETRY_FAILED_OLDER_THAN_MINUTES:-}

retry_failed_value="false"
if [ "${RETRY_FAILED_ENABLED}" = "1" ] || [ "${RETRY_FAILED_ENABLED}" = "true" ]; then
  retry_failed_value="true"
fi

retry_failed_only_retryable_value="true"
if [ "${RETRY_FAILED_ONLY_RETRYABLE}" = "0" ] || [ "${RETRY_FAILED_ONLY_RETRYABLE}" = "false" ]; then
  retry_failed_only_retryable_value="false"
fi

url="$CORE_API_URL/api/v1/contract-jobs/maintenance?dry_run=false&limit_each=${LIMIT_EACH}&stale_minutes=${STALE_MINUTES}&reset_stale=true&finalize_exhausted_new=true&retry_failed=${retry_failed_value}&retry_failed_only_retryable=${retry_failed_only_retryable_value}"
if [ -n "${RETRY_FAILED_OLDER_THAN_MINUTES}" ]; then
  url="${url}&retry_failed_older_than_minutes=${RETRY_FAILED_OLDER_THAN_MINUTES}"
fi

curl -sf -X POST "${url}" \
  -H "X-API-Key: ${API_KEY_ADMIN:?API_KEY_ADMIN is required}" >/dev/null
