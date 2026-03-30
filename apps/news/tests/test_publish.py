from __future__ import annotations

from datetime import datetime, timedelta, timezone

from news.publish import _autofill_publish_at, _demote_stale_scheduled_posts, _promote_ready_posts_for_idle_queue
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
    def __init__(self, *, ready_rows=None, scheduled_rows=None) -> None:
        self._ready_rows = ready_rows
        self._scheduled_rows = scheduled_rows
        self.patched: list[tuple[str, dict[str, str]]] = []

    def list_posts(self, limit: int = 20, status: str | None = None, newest_first: bool = False, offset: int = 0):
        _ = (limit, newest_first, offset)
        if status == "ready":
            return _FakeResponse(self._ready_rows[:limit])
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
