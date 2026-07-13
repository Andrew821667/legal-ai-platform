from __future__ import annotations

from datetime import UTC, datetime, timedelta

from news.active_queue import rebalance_active_publish_queue


class _FakeResponse:
    def __init__(self, payload) -> None:
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, *, scheduled_rows, ready_rows) -> None:
        self._scheduled_rows = scheduled_rows
        self._ready_rows = ready_rows
        self.patched: list[tuple[str, dict[str, str]]] = []

    def list_posts(self, limit: int = 20, status: str | None = None, newest_first: bool = False, offset: int = 0):
        _ = (limit, newest_first, offset)
        if status == "scheduled":
            return _FakeResponse(self._scheduled_rows)
        if status == "ready":
            return _FakeResponse(self._ready_rows)
        raise AssertionError(f"unexpected status {status}")

    def patch_post(self, post_id: str, payload: dict[str, str]):
        self.patched.append((post_id, payload))
        return _FakeResponse({})


def test_rebalance_active_publish_queue_demotes_extra_scheduled_and_promotes_missing(monkeypatch) -> None:
    now_utc = datetime.now(UTC)
    monkeypatch.setattr(
        "news.active_queue.next_active_slot_by_kind",
        lambda **kwargs: {
            "daily": now_utc + timedelta(hours=1),
            "weekly_review": now_utc + timedelta(days=2),
        },
    )
    client = _FakeClient(
        scheduled_rows=[
            {"id": "daily-1", "format_type": "daily", "publish_at": (now_utc + timedelta(hours=5)).isoformat()},
            {"id": "daily-2", "format_type": "daily", "publish_at": (now_utc + timedelta(hours=6)).isoformat()},
        ],
        ready_rows=[
            {"id": "weekly-1", "format_type": "weekly_review", "publish_at": (now_utc + timedelta(days=4)).isoformat()},
        ],
    )

    result = rebalance_active_publish_queue(client)

    assert result == {"demoted": 1, "promoted": 1, "rescheduled": 1}
    assert ("daily-2", {"status": "ready"}) in client.patched
    assert ("weekly-1", {"status": "scheduled", "publish_at": (now_utc + timedelta(days=2)).isoformat()}) in client.patched


def test_rebalance_active_publish_queue_keeps_due_scheduled_post(monkeypatch) -> None:
    now_utc = datetime.now(UTC)
    monkeypatch.setattr(
        "news.active_queue.next_active_slot_by_kind",
        lambda **kwargs: {"daily": now_utc + timedelta(hours=1)},
    )
    client = _FakeClient(
        scheduled_rows=[
            {"id": "daily-due", "format_type": "daily", "publish_at": (now_utc - timedelta(minutes=5)).isoformat()},
            {"id": "daily-future", "format_type": "daily", "publish_at": (now_utc + timedelta(hours=6)).isoformat()},
        ],
        ready_rows=[],
    )

    result = rebalance_active_publish_queue(client)

    assert result == {"demoted": 1, "promoted": 0, "rescheduled": 0}
    assert ("daily-future", {"status": "ready"}) in client.patched
    assert all(post_id != "daily-due" for post_id, _ in client.patched)


def test_rebalance_active_publish_queue_keeps_pending_retry(monkeypatch) -> None:
    now_utc = datetime.now(UTC)
    monkeypatch.setattr(
        "news.active_queue.next_active_slot_by_kind",
        lambda **kwargs: {"practice": now_utc + timedelta(days=7)},
    )
    client = _FakeClient(
        scheduled_rows=[
            {
                "id": "practice-retry",
                "format_type": "practice",
                "publish_at": (now_utc + timedelta(minutes=10)).isoformat(),
                "attempts": 1,
                "last_error": "Telegram connection timed out",
            }
        ],
        ready_rows=[],
    )

    result = rebalance_active_publish_queue(client)

    assert result == {"demoted": 0, "promoted": 0, "rescheduled": 0}
    assert client.patched == []
