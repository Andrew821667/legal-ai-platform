"""Measure channel silence by delivery time, not the editable schedule."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen

UTC = timezone.utc  # noqa: UP017 - The host watchdog uses macOS Python 3.9.


def channel_silence_hours(
    api_base: str, api_key: str, *, now: datetime | None = None
) -> int:
    latest = None
    offset = 0
    while True:
        req = Request(
            f"{api_base.rstrip('/')}/api/v1/scheduled-posts"
            f"?status=posted&limit=100&offset={offset}",
            headers={"X-API-Key": api_key},
        )
        with urlopen(req, timeout=15) as response:
            rows = json.load(response)
        for row in rows:
            raw = str(row.get("posted_at") or "").strip()
            if not raw:
                continue
            try:
                at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if at.tzinfo is None:
                at = at.replace(tzinfo=UTC)
            if latest is None or at > latest:
                latest = at
        if len(rows) < 100:
            break
        offset += len(rows)
    if latest is None:
        return -1
    now = now or datetime.now(UTC)
    return max(0, int((now - latest).total_seconds() // 3600))


if __name__ == "__main__":
    print(channel_silence_hours(sys.argv[1], os.environ["API_KEY_ADMIN"]))
