from __future__ import annotations

from news.publish_actions import (
    build_batch_result_lines,
    build_draft_batch_publish_state,
    build_draft_publish_state,
    build_pending_batch_publish_state,
    build_pending_delete_state,
    clear_context_states,
    extract_batch_post_ids,
    extract_post_ids,
    normalize_batch_scope,
    normalize_reason,
)


def test_extract_batch_post_ids_and_post_ids() -> None:
    rows = [{"id": "1"}, {"id": "2"}, {"id": "3"}, {"id": "4"}]
    assert extract_batch_post_ids(rows, mode="page", batch_mode_limit=lambda mode: None) == ["1", "2", "3", "4"]
    assert extract_batch_post_ids(rows, mode="top3", batch_mode_limit=lambda mode: 3 if mode == "top3" else None) == [
        "1",
        "2",
        "3",
    ]
    assert extract_post_ids(["10", "", None, 12]) == ["10", "12"]
    assert extract_post_ids("not-list") == []


def test_normalize_batch_scope_and_reason() -> None:
    assert normalize_batch_scope(
        queue_filter="all",
        offset="12",
        mode="top5",
        manual_queue_filters=("due", "all"),
        batch_publish_modes=("page", "top3", "top5"),
    ) == ("all", 12, "top5")
    assert normalize_batch_scope(
        queue_filter="unknown",
        offset="oops",
        mode="bad",
        manual_queue_filters=("due", "all"),
        batch_publish_modes=("page", "top3", "top5"),
    ) == ("due", 0, "page")
    assert normalize_reason("  срочно   для  клиента ", reason_normalizer=lambda text: " ".join(text.split())) == "срочно для клиента"


def test_state_builders_and_clear_context() -> None:
    assert build_pending_batch_publish_state(queue_filter="due", offset=8, mode="top3", post_ids=["1", "2"]) == {
        "queue_filter": "due",
        "offset": 8,
        "mode": "top3",
        "post_ids": ["1", "2"],
    }
    assert build_draft_batch_publish_state(
        queue_filter="due",
        offset=8,
        mode="top3",
        post_ids=["1", "2"],
        reason="manual publish",
    ) == {
        "queue_filter": "due",
        "offset": 8,
        "mode": "top3",
        "post_ids": ["1", "2"],
        "reason": "manual publish",
    }
    assert build_pending_delete_state(post_id="42", status="review", offset=0) == {
        "post_id": "42",
        "status": "review",
        "offset": 0,
    }
    assert build_pending_delete_state(post_id="42", status="review", offset=0, reason="noise") == {
        "post_id": "42",
        "status": "review",
        "offset": 0,
        "reason": "noise",
    }
    assert build_draft_publish_state(post_id="42", status="review", offset=0, reason="manual") == {
        "post_id": "42",
        "status": "review",
        "offset": 0,
        "reason": "manual",
    }

    user_data = {"a": 1, "b": 2, "c": 3}
    clear_context_states(user_data, ("a", "c", "missing"))
    assert user_data == {"b": 2}


def test_build_batch_result_lines() -> None:
    lines = build_batch_result_lines(
        success_count=3,
        failed=["9", "10"],
        mode="top3",
        batch_mode_label=lambda mode: {"top3": "топ-3"}[mode],
    )
    assert lines[0] == "Пакетная публикация завершена."
    assert "Успешно: 3" in lines
    assert "С ошибкой: 2" in lines
    assert "Режим: топ-3" in lines
    assert "ID с ошибками: 9, 10" in lines
