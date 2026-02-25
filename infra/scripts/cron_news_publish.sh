#!/bin/bash
set -euo pipefail

LOCK_FILE=${LOCK_FILE:-/tmp/news-publisher.lock}
exec 200>"$LOCK_FILE"
flock -n 200 || exit 0

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

uv run --package news python -m news.publish
