#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

uv run --package core-api python -m core_api.cli cleanup-idempotency --hours 24
