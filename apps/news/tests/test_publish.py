from __future__ import annotations

from datetime import UTC, datetime, timedelta

from news.publish import (
    TelegramRequestError,
    _autofill_publish_at,
    _demote_stale_scheduled_posts,
    _normalize_text_before_publish,
    _promote_due_editorial_posts_for_idle_publisher,
    _promote_ready_posts_for_idle_queue,
    _retryable_publish_patch,
)
from news.publish import (
    main as publish_main,
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
    def __init__(self, *, ready_rows=None, review_rows=None, scheduled_rows=None, posted_rows=None) -> None:
        self._ready_rows = ready_rows or []
        self._review_rows = review_rows or []
        self._scheduled_rows = scheduled_rows
        self._posted_rows = posted_rows or []
        self.patched: list[tuple[str, dict[str, object]]] = []

    def list_posts(self, limit: int = 20, status: str | None = None, newest_first: bool = False, offset: int = 0):
        _ = (limit, newest_first, offset)
        if status == "ready":
            return _FakeResponse(self._ready_rows[:limit])
        if status == "review":
            return _FakeResponse(self._review_rows[:limit])
        if status == "scheduled":
            return _FakeResponse(self._scheduled_rows[:limit])
        if status == "posted":
            return _FakeResponse(self._posted_rows[:limit])
        raise AssertionError(f"unexpected status {status}")

    def patch_post(self, post_id: str, payload: dict[str, str]):
        self.patched.append((post_id, payload))
        return _FakeResponse({})


class _FakeMainClient(_FakeClient):
    def __init__(self) -> None:
        super().__init__(
            ready_rows=[{"id": "ready-1"}],
            review_rows=[{"id": "review-1"}],
            scheduled_rows=[],
        )
        self.claims = 0

    def list_automation_controls(self, scope: str | None = None):
        _ = scope
        return _FakeResponse([])

    def claim_posts(self, limit: int):
        _ = limit
        self.claims += 1
        return _FakeResponse([], status_code=204)


def test_autofill_publish_at_keeps_future_publish_time() -> None:
    now_utc = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
    future = now_utc + timedelta(hours=5)
    row = {"publish_at": future.isoformat()}

    result = _autofill_publish_at(row, queue_index=0, now_utc=now_utc)

    assert result == future.isoformat()


def test_autofill_publish_at_shifts_past_review_post_forward() -> None:
    now_utc = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
    past = now_utc - timedelta(hours=2)
    row = {"publish_at": past.isoformat()}

    result = _autofill_publish_at(row, queue_index=1, now_utc=now_utc)

    assert datetime.fromisoformat(result) == now_utc + timedelta(hours=2)


def test_promote_ready_posts_for_idle_queue() -> None:
    now_utc = datetime.now(UTC)
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


def test_due_editorial_fallback_promotes_due_ready_before_review(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    client = _FakeClient(
        ready_rows=[
            {"id": "future-ready", "publish_at": (now_utc + timedelta(hours=2)).isoformat()},
            {"id": "due-ready", "publish_at": datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat()},
        ],
        review_rows=[{"id": "due-review", "publish_at": datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat()}],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 1
    assert client.patched == [("due-ready", {"status": "scheduled", "last_error": None})]


def test_due_editorial_fallback_promotes_due_review_when_ready_has_no_due_posts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    client = _FakeClient(
        ready_rows=[{"id": "future-ready", "publish_at": (now_utc + timedelta(hours=2)).isoformat()}],
        review_rows=[{"id": "due-review", "publish_at": datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat()}],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 1
    assert client.patched == [("due-review", {"status": "scheduled", "last_error": None})]


def test_due_editorial_fallback_skips_future_review_posts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    client = _FakeClient(
        ready_rows=[],
        review_rows=[{"id": "future-review", "publish_at": (now_utc + timedelta(hours=2)).isoformat()}],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 0
    assert client.patched == []


def test_due_editorial_fallback_skips_posts_outside_current_slot_window(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    client = _FakeClient(
        ready_rows=[],
        review_rows=[
            {"id": "stale-review", "publish_at": datetime(2026, 5, 13, 9, 0, tzinfo=UTC).isoformat()},
            {"id": "fresh-review", "publish_at": datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat()},
        ],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 1
    assert client.patched == [("fresh-review", {"status": "scheduled", "last_error": None})]


def test_due_editorial_fallback_skips_slot_that_was_already_posted(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    slot_at = datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat()
    client = _FakeClient(
        ready_rows=[],
        review_rows=[{"id": "due-review", "publish_at": slot_at}],
        posted_rows=[{"id": "posted-review", "publish_at": slot_at}],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 0
    assert client.patched == []


def test_main_skips_idle_fallback_when_startup_grace_is_active(monkeypatch) -> None:
    client = _FakeMainClient()

    monkeypatch.setattr("news.publish.CoreClient", lambda *_args, **_kwargs: client)
    monkeypatch.setattr("news.publish.rebalance_active_publish_queue", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(settings, "api_key_news", "test-key")

    result = publish_main(allow_idle_fallback=False)

    assert result == 0
    assert client.claims == 1
    assert client.patched == []


def test_main_ignores_unsafe_idle_fallback_after_startup_grace(monkeypatch) -> None:
    client = _FakeMainClient()

    monkeypatch.setattr("news.publish.CoreClient", lambda *_args, **_kwargs: client)
    monkeypatch.setattr("news.publish.rebalance_active_publish_queue", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(settings, "api_key_news", "test-key")
    monkeypatch.setattr(settings, "news_publish_idle_fallback_enabled", True)

    result = publish_main(allow_idle_fallback=True)

    assert result == 0
    assert client.claims == 1
    assert client.patched == []


def test_main_disables_idle_fallback_by_default(monkeypatch) -> None:
    client = _FakeMainClient()

    monkeypatch.setattr("news.publish.CoreClient", lambda *_args, **_kwargs: client)
    monkeypatch.setattr("news.publish.rebalance_active_publish_queue", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(settings, "api_key_news", "test-key")
    monkeypatch.setattr(settings, "news_publish_idle_fallback_enabled", False)

    result = publish_main(allow_idle_fallback=True)

    assert result == 0
    assert client.claims == 1
    assert client.patched == []


def test_do_not_promote_stale_or_distant_ready_posts_for_idle_queue() -> None:
    now_utc = datetime.now(UTC)
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
    now_utc = datetime.now(UTC)
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
        now_utc = datetime(2026, 4, 13, 6, 5, tzinfo=UTC)
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
        now_utc=datetime(2026, 4, 13, 6, 5, tzinfo=UTC),
    )

    assert patch is None


def test_retryable_publish_patch_ignores_non_retryable_error() -> None:
    patch = _retryable_publish_patch(
        {"attempts": 0, "max_attempts": 3},
        TelegramRequestError("bad request", retryable=False),
        now_utc=datetime(2026, 4, 13, 6, 5, tzinfo=UTC),
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


def test_normalize_text_before_publish_adds_vpn_notice_for_external_source() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста.\n\n"
        '<b>Источник</b>: <a href="https://example.com/article">оригинал</a>\n'
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(original)

    assert "отключите VPN" in normalized
    assert normalized.index("оригинал") < normalized.index("отключите VPN")


def test_normalize_text_before_publish_skips_vpn_notice_for_telegram_links() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста.\n\n"
        '<b>Источник</b>: <a href="https://t.me/ai_verdict/42">пост</a>\n'
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(original)

    assert "отключите VPN" not in normalized


def test_normalize_text_before_publish_adds_missing_footer_for_applicable_ready_post() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста про рынок Legal AI и внедрение в юрфункции.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(
        original,
        {"title": "Заголовок", "format_type": "daily", "cta_type": "soft", "rubric": "contracts"},
    )

    assert "<b>Следующий шаг</b>" in normalized
    assert "https://t.me/legal_ai_helper_new_bot" in normalized
    assert normalized.index("<b>Следующий шаг</b>") < normalized.index("<b>Источник</b>")


def test_normalize_text_before_publish_does_not_force_footer_when_not_applicable() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста про общий рыночный сигнал без явного сценария внедрения.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(
        original,
        {"title": "Заголовок", "format_type": "daily", "cta_type": "soft", "rubric": "market"},
    )

    assert "<b>Следующий шаг</b>" not in normalized


def test_normalize_text_before_publish_respects_disabled_footer_control() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(
        original,
        {"title": "Заголовок", "format_type": "daily", "cta_type": "soft", "rubric": "market"},
        intelligent_footer=False,
    )

    assert "<b>Следующий шаг</b>" not in normalized


def test_normalize_text_before_publish_keeps_weekly_review_footerless() -> None:
    original = (
        "<b>Обзор недели</b>\n\n"
        "1. Первый сигнал.\n"
        "2. Второй сигнал.\n\n"
        "<b>Источник</b>: внутренняя подборка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(
        original,
        {"title": "Обзор недели", "format_type": "weekly_review", "cta_type": "soft", "rubric": "market"},
    )

    assert "<b>Следующий шаг</b>" not in normalized
