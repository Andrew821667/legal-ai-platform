from __future__ import annotations

from collections.abc import Callable, MutableMapping, Sequence
from typing import Any


BatchModeLimit = Callable[[str], int | None]
BatchModeLabel = Callable[[str], str]
ReasonNormalizer = Callable[[str], str]


def extract_batch_post_ids(
    rows: Sequence[dict[str, Any]],
    *,
    mode: str,
    batch_mode_limit: BatchModeLimit,
) -> list[str]:
    selected_rows = rows
    limit = batch_mode_limit(mode)
    if limit is not None:
        selected_rows = rows[:limit]
    return [str(row.get("id")) for row in selected_rows if row.get("id")]


def normalize_batch_scope(
    *,
    queue_filter: str,
    offset: object,
    mode: str,
    manual_queue_filters: Sequence[str],
    batch_publish_modes: Sequence[str],
) -> tuple[str, int, str]:
    normalized_queue_filter = queue_filter if queue_filter in manual_queue_filters else "due"
    try:
        normalized_offset = int(offset)
    except (TypeError, ValueError):
        normalized_offset = 0
    normalized_mode = mode if mode in batch_publish_modes else "page"
    return normalized_queue_filter, normalized_offset, normalized_mode


def normalize_reason(value: object, *, reason_normalizer: ReasonNormalizer) -> str:
    return reason_normalizer(str(value or ""))


def extract_post_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def build_pending_batch_publish_state(
    *,
    queue_filter: str,
    offset: int,
    mode: str,
    post_ids: list[str],
) -> dict[str, Any]:
    return {
        "queue_filter": queue_filter,
        "offset": offset,
        "mode": mode,
        "post_ids": post_ids,
    }


def build_draft_batch_publish_state(
    *,
    queue_filter: str,
    offset: int,
    mode: str,
    post_ids: list[str],
    reason: str,
) -> dict[str, Any]:
    state = build_pending_batch_publish_state(
        queue_filter=queue_filter,
        offset=offset,
        mode=mode,
        post_ids=post_ids,
    )
    state["reason"] = reason
    return state


def build_pending_delete_state(
    *,
    post_id: str,
    status: str,
    offset: int,
    reason: str | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {"post_id": post_id, "status": status, "offset": offset}
    if reason:
        state["reason"] = reason
    return state


def build_draft_publish_state(
    *,
    post_id: str,
    status: str,
    offset: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "post_id": post_id,
        "status": status,
        "offset": offset,
        "reason": reason,
    }


def clear_context_states(user_data: MutableMapping[str, Any], keys: Sequence[str]) -> None:
    for key in keys:
        user_data.pop(key, None)


def build_batch_result_lines(
    *,
    success_count: int,
    failed: Sequence[str],
    mode: str,
    batch_mode_label: BatchModeLabel,
) -> list[str]:
    lines = [
        "Пакетная публикация завершена.",
        f"Успешно: {success_count}",
        f"С ошибкой: {len(failed)}",
        f"Режим: {batch_mode_label(mode)}",
    ]
    if failed:
        lines.append("ID с ошибками: " + ", ".join(failed[:5]))
    lines.append("")
    return lines
