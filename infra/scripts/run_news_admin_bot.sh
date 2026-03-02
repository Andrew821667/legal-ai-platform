#!/bin/bash
set -euo pipefail

LOCK_FILE=${LOCK_FILE:-/tmp/news-admin-bot.lock}
exec 201>"$LOCK_FILE"
flock -n 201 || exit 0

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

uv run --package news python -m news.admin_bot
