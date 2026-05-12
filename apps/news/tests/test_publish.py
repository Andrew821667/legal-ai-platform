from __future__ import annotations

from datetime import datetime, timedelta, timezone

from news.publish import (
    TelegramRequestError,
    _autofill_publish_at,
    _demote_stale_scheduled_posts,
    _normalize_text_before_publish,
    _promote_fallback_posts_for_idle_publisher,
    _promote_ready_posts_for_idle_queue,
    _retryable_publish_patch,
)
from news.settings import settings


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, *, ready_rows=None, review_rows=None, scheduled_rows=None) -> None:
        self._ready_rows = ready_rows or []
        self._review_rows = review_rows or []
        self._scheduled_rows = scheduled_rows
        self.patched: list[tuple[str, dict[str, object]]] = []

    def list_posts(self, limit: int = 20, status: str | None = None, newest_first: bool = False, offset: int = 0):
        _ = (limit, newest_first, offset)
        if status == "ready":
            return _FakeResponse(self._ready_rows[:limit])
        if status == "review":
            return _FakeResponse(self._review_rows[:limit])
        if status == "scheduled":
            return _FakeResponse(self._scheduled_rows[:limit])
        raise AssertionError(f"unexpected status {status}")

    def patch_post(self, post_id: str, payload: dict[str, str]):
        self.patched.append((post_id, payload))
        return _FakeResponse({})


def test_autofill_publish_at_keeps_future_publish_time() -> None:
    now_utc = datetime(2026, 3, 16, 12, 0, tzinfo=timezone.utc)
    future = now_utc + timedelta(hours=5)
    row = {"publish_at": future.isoformat()}

    result = _autofill_publish_at(row, queue_index=0, now_utc=now_utc)

    assert result == future.isoformat()


def test_autofill_publish_at_shifts_past_review_post_forward() -> None:
    now_utc = datetime(2026, 3, 16, 12, 0, tzinfo=timezone.utc)
    past = now_utc - timedelta(hours=2)
    row = {"publish_at": past.isoformat()}

    result = _autofill_publish_at(row, queue_index=1, now_utc=now_utc)

    assert datetime.fromisoformat(result) == now_utc + timedelta(hours=2)


def test_promote_ready_posts_for_idle_queue() -> None:
    now_utc = datetime.now(timezone.utc)
    client = _FakeClient(
        ready_rows=[
            {"id": "r1", "publish_at": (now_utc - timedelta(hours=1)).isoformat()},
            {"id": "r2", "publish_at": (now_utc + timedelta(hours=3)).isoformat()},
        ],
    )

    promoted = _promote_ready_posts_for_idle_queue(client, limit=1)

    assert promoted == 2
    assert [post_id for post_id, _ in client.patched] == ["r1", "r2"]
    assert client.patched[0][1]["status"] == "scheduled"
    assert client.patched[1][1]["status"] == "scheduled"


def test_idle_publisher_promotes_ready_before_review() -> None:
    now_utc = datetime(2026, 5, 12, 15, 0, tzinfo=timezone.utc)
    client = _FakeClient(
        ready_rows=[{"id": "ready-1"}],
        review_rows=[{"id": "review-1"}],
    )

    promoted = _promote_fallback_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 1
    assert client.patched == [
        (
            "ready-1",
            {"status": "scheduled", "publish_at": now_utc.isoformat(), "last_error": None},
        )
    ]


def test_idle_publisher_promotes_review_when_ready_empty() -> None:
    now_utc = datetime(2026, 5, 12, 15, 0, tzinfo=timezone.utc)
    client = _FakeClient(
        ready_rows=[],
        review_rows=[{"id": "review-1"}],
    )

    promoted = _promote_fallback_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 1
    assert client.patched == [
        (
            "review-1",
            {"status": "scheduled", "publish_at": now_utc.isoformat(), "last_error": None},
        )
    ]


def test_do_not_promote_stale_or_distant_ready_posts_for_idle_queue() -> None:
    now_utc = datetime.now(timezone.utc)
    client = _FakeClient(
        ready_rows=[
            {"id": "stale", "publish_at": (now_utc - timedelta(days=3)).isoformat()},
            {"id": "distant", "publish_at": (now_utc + timedelta(days=3)).isoformat()},
        ],
    )

    promoted = _promote_ready_posts_for_idle_queue(client, limit=3)

    assert promoted == 0
    assert client.patched == []


def test_demote_stale_scheduled_posts_to_ready() -> None:
    now_utc = datetime.now(timezone.utc)
    client = _FakeClient(
        scheduled_rows=[
            {"id": "old", "publish_at": (now_utc - timedelta(hours=7)).isoformat()},
            {"id": "fresh", "publish_at": (now_utc - timedelta(hours=2)).isoformat()},
            {"id": "future", "publish_at": (now_utc + timedelta(hours=2)).isoformat()},
        ],
    )

    original = settings.news_publish_max_overdue_minutes
    settings.news_publish_max_overdue_minutes = 360
    try:
        demoted = _demote_stale_scheduled_posts(client)
    finally:
        settings.news_publish_max_overdue_minutes = original

    assert demoted == 1
    assert client.patched == [("old", {"status": "ready"})]


def test_retryable_publish_patch_requeues_transient_telegram_failure() -> None:
    original = settings.news_retry_failed_after_minutes
    settings.news_retry_failed_after_minutes = 15
    try:
        now_utc = datetime(2026, 4, 13, 6, 5, tzinfo=timezone.utc)
        patch = _retryable_publish_patch(
            {"attempts": 0, "max_attempts": 3},
            TelegramRequestError("dns fail", retryable=True),
            now_utc=now_utc,
        )
    finally:
        settings.news_retry_failed_after_minutes = original

    assert patch is not None
    assert patch["status"] == "scheduled"
    assert patch["attempts"] == 1
    assert datetime.fromisoformat(patch["publish_at"]) == now_utc + timedelta(minutes=15)


def test_retryable_publish_patch_stops_after_max_attempts() -> None:
    patch = _retryable_publish_patch(
        {"attempts": 2, "max_attempts": 3},
        TelegramRequestError("dns fail", retryable=True),
        now_utc=datetime(2026, 4, 13, 6, 5, tzinfo=timezone.utc),
    )

    assert patch is None


def test_retryable_publish_patch_ignores_non_retryable_error() -> None:
    patch = _retryable_publish_patch(
        {"attempts": 0, "max_attempts": 3},
        TelegramRequestError("bad request", retryable=False),
        now_utc=datetime(2026, 4, 13, 6, 5, tzinfo=timezone.utc),
    )

    assert patch is None


def test_normalize_text_before_publish_collapses_duplicate_footer_blocks() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста.\n\n"
        "Обсудите внедрение с Асистентом AI Verdict.\n\n"
        "<b>Следующий шаг</b>\nОбсудите с Асистентом AI Verdict.\n\n"
        "<b>Следующий шаг</b>\nНапишите в @legal_ai_helper_new_bot.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(original)

    assert normalized.count("<b>Следующий шаг</b>") == 1
    assert normalized.count("https://t.me/legal_ai_helper_new_bot") == 1
    assert "Асистент" not in normalized
    assert "Напишите в" not in normalized
    assert normalized.index("<b>Следующий шаг</b>") < normalized.index("<b>Источник</b>")
