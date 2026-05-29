from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from news.generate_loop import _cleanup_expired_editorial_posts, _weekly_review_retention_days
from news.settings import settings


class _FakeResponse:
    def __init__(self, payload: list[dict[str, Any]]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict[str, Any]]:
        return self._payload


class _FakeClient:
    def __init__(self, pages: dict[tuple[str, int], list[dict[str, Any]]]) -> None:
        self._pages = pages
        self.patched: list[tuple[str, dict[str, Any]]] = []

    def list_posts(
        self,
        limit: int = 20,
        status: str | None = None,
        newest_first: bool = False,
        offset: int = 0,
    ) -> _FakeResponse:
        assert newest_first is False
        assert limit == 100
        return _FakeResponse(self._pages.get((status or "", offset), []))

    def patch_post(self, post_id: str, payload: dict[str, Any]) -> _FakeResponse:
        self.patched.append((post_id, payload))
        return _FakeResponse([])


def _iso_days_ago(days: int) -> str:
    return (datetime.now().astimezone() - timedelta(days=days)).isoformat()


def _iso_days_from_now(days: int) -> str:
    return (datetime.now().astimezone() + timedelta(days=days)).isoformat()


def test_cleanup_expired_editorial_posts_removes_stale_draft_and_review() -> None:
    client = _FakeClient(
        {
            ("draft", 0): [
                {"id": "draft-old", "created_at": _iso_days_ago(6), "format_type": "daily"},
                {
                    "id": "weekly-keep",
                    "created_at": _iso_days_ago(settings.news_weekly_review_min_retention_days - 1),
                    "format_type": "weekly_review",
                },
            ],
            ("review", 0): [
                {"id": "review-old", "created_at": _iso_days_ago(4), "format_type": "longread"},
            ],
        }
    )

    cleaned = _cleanup_expired_editorial_posts(client, retention_days=3)

    assert cleaned == 2
    assert ("draft-old", {"status": "failed", "last_error": "expired_editorial_cleanup"}) in client.patched
    assert ("review-old", {"status": "failed", "last_error": "expired_editorial_cleanup"}) in client.patched
    assert all(post_id != "weekly-keep" for post_id, _ in client.patched)


def test_cleanup_expired_editorial_posts_keeps_future_scheduled_review() -> None:
    client = _FakeClient(
        {
            ("draft", 0): [],
            ("review", 0): [
                {
                    "id": "future-review",
                    "created_at": _iso_days_ago(6),
                    "publish_at": _iso_days_from_now(1),
                    "format_type": "daily",
                },
                {
                    "id": "past-review",
                    "created_at": _iso_days_ago(6),
                    "publish_at": _iso_days_ago(4),
                    "format_type": "daily",
                },
            ],
        }
    )

    cleaned = _cleanup_expired_editorial_posts(client, retention_days=3)

    assert cleaned == 1
    assert client.patched == [("past-review", {"status": "failed", "last_error": "expired_editorial_cleanup"})]


def test_cleanup_expired_editorial_posts_keeps_recent_due_review_by_publish_at() -> None:
    client = _FakeClient(
        {
            ("draft", 0): [],
            ("review", 0): [
                {
                    "id": "due-review",
                    "created_at": _iso_days_ago(6),
                    "publish_at": _iso_days_ago(1),
                    "format_type": "daily",
                },
            ],
        }
    )

    cleaned = _cleanup_expired_editorial_posts(client, retention_days=3)

    assert cleaned == 0
    assert client.patched == []


def test_cleanup_expired_editorial_posts_scans_later_pages_for_shorter_retention() -> None:
    weekly_rows = [
        {
            "id": f"weekly-{index}",
            "created_at": _iso_days_ago(settings.news_weekly_review_min_retention_days - 1),
            "format_type": "weekly_review",
        }
        for index in range(100)
    ]
    client = _FakeClient(
        {
            ("draft", 0): weekly_rows,
            ("draft", 100): [
                {"id": "daily-stale", "created_at": _iso_days_ago(4), "format_type": "daily"},
            ],
            ("review", 0): [],
        }
    )

    cleaned = _cleanup_expired_editorial_posts(client, retention_days=3)

    assert cleaned == 1
    assert client.patched == [("daily-stale", {"status": "failed", "last_error": "expired_editorial_cleanup"})]
    assert _weekly_review_retention_days(3) == settings.news_weekly_review_min_retention_days
