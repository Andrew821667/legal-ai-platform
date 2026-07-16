from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from news.settings import settings
from news.strategy import build_schedule_window, publication_kind_from_format_type

ACTIVE_PUBLICATION_KINDS = ("daily", "weekly_review", "longread", "practice")
ACTIVE_QUEUE_SCAN_LIMIT = 100


def parse_post_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def row_publication_kind(row: dict[str, object]) -> str:
    return publication_kind_from_format_type(str(row.get("format_type") or ""))


def next_active_slot_by_kind(*, control_rows: list[dict[str, object]] | None = None) -> dict[str, datetime]:
    now_local = datetime.now(ZoneInfo(settings.tz_name))
    result: dict[str, datetime] = {}
    for slot in build_schedule_window(now_local, days=21, control_rows=control_rows, future_only=True):
        kind = slot.publication_kind
        if kind not in ACTIVE_PUBLICATION_KINDS or kind in result:
            continue
        result[kind] = slot.publish_at_local.astimezone(UTC)
        if len(result) == len(ACTIVE_PUBLICATION_KINDS):
            break
    return result


def rebalance_active_publish_queue(
    client,
    *,
    control_rows: list[dict[str, object]] | None = None,
    preferred_post_id: str | None = None,
    scan_limit: int = ACTIVE_QUEUE_SCAN_LIMIT,
) -> dict[str, int]:
    next_slot_map = next_active_slot_by_kind(control_rows=control_rows)
    scheduled_response = client.list_posts(limit=scan_limit, status="scheduled", newest_first=False)
    scheduled_response.raise_for_status()
    ready_response = client.list_posts(limit=scan_limit, status="ready", newest_first=False)
    ready_response.raise_for_status()

    scheduled_rows = list(scheduled_response.json() or [])
    ready_rows = list(ready_response.json() or [])
    now_utc = datetime.now(UTC)

    def _row_time(row: dict[str, object]) -> datetime:
        return parse_post_datetime(row.get("publish_at")) or datetime.max.replace(tzinfo=UTC)

    retry_guard = timedelta(
        minutes=max(settings.news_retry_failed_after_minutes, 1),
        seconds=max(settings.news_publish_interval_seconds, 0),
    )

    def _is_pending_retry(row: dict[str, object]) -> bool:
        row_time = parse_post_datetime(row.get("publish_at"))
        if row_time is None or not (now_utc < row_time <= now_utc + retry_guard):
            return False
        return int(row.get("attempts") or 0) > 0 and bool(str(row.get("last_error") or "").strip())

    by_kind: dict[str, list[dict[str, object]]] = {}
    for row in scheduled_rows:
        kind = row_publication_kind(row)
        if kind not in next_slot_map:
            continue
        by_kind.setdefault(kind, []).append(row)

    demoted = 0
    promoted = 0
    rescheduled = 0

    for kind, rows in by_kind.items():
        rows.sort(key=_row_time)
        due_rows = [row for row in rows if (_time := parse_post_datetime(row.get("publish_at"))) and _time <= now_utc]
        retry_rows = [row for row in rows if _is_pending_retry(row)]
        keep_row: dict[str, object]
        if due_rows:
            keep_row = due_rows[0]
        elif retry_rows:
            keep_row = retry_rows[0]
        elif preferred_post_id is not None:
            preferred = next((row for row in rows if str(row.get("id") or "") == preferred_post_id), None)
            keep_row = preferred or rows[0]
        else:
            keep_row = rows[0]

        keep_id = str(keep_row.get("id") or "").strip()
        keep_time = parse_post_datetime(keep_row.get("publish_at"))
        desired_time = next_slot_map[kind]
        if keep_id and not _is_pending_retry(keep_row) and (
            keep_time is None or (keep_time > now_utc and keep_time != desired_time)
        ):
            client.patch_post(
                keep_id,
                {"status": "scheduled", "publish_at": desired_time.isoformat()},
            ).raise_for_status()
            rescheduled += 1

        for row in rows:
            row_id = str(row.get("id") or "").strip()
            if not row_id or row_id == keep_id:
                continue
            client.patch_post(row_id, {"status": "ready"}).raise_for_status()
            demoted += 1

    active_scheduled_ids = {
        str(rows[0].get("id") or "").strip()
        for kind, rows in by_kind.items()
        if rows
    }

    for kind, desired_time in next_slot_map.items():
        if kind in by_kind and by_kind[kind]:
            continue
        candidates = [row for row in ready_rows if row_publication_kind(row) == kind]
        candidates.sort(key=_row_time)
        if not candidates:
            continue
        candidate_id = str(candidates[0].get("id") or "").strip()
        if not candidate_id or candidate_id in active_scheduled_ids:
            continue
        client.patch_post(
            candidate_id,
            {"status": "scheduled", "publish_at": desired_time.isoformat()},
        ).raise_for_status()
        promoted += 1

    return {"demoted": demoted, "promoted": promoted, "rescheduled": rescheduled}
