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


def _slots(*items: tuple[str, datetime]):
    from types import SimpleNamespace

    return [SimpleNamespace(publication_kind=kind, publish_at_local=when) for kind, when in items]


def test_next_slot_skips_slot_taken_by_manual_post(monkeypatch) -> None:
    """Регрессия 23.09: ручной пост стоял на 18:00 — вечернем слоте ежедневных
    новостей, — и очередь поставила туда же свой пост. Вышли оба с разницей в
    пять минут. Теперь слот занят, и ежедневная новость идёт на следующий."""
    from news.active_queue import next_active_slot_by_kind

    base = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=2)
    evening = base
    morning = base + timedelta(hours=15)
    monkeypatch.setattr(
        "news.active_queue.build_schedule_window",
        lambda *args, **kwargs: _slots(("daily", evening), ("daily", morning)),
    )

    assert next_active_slot_by_kind()["daily"] == evening
    assert next_active_slot_by_kind(occupied_times=[evening])["daily"] == morning


def test_manual_post_near_slot_also_takes_it(monkeypatch) -> None:
    """17:50 и 18:00 — это те же два поста подряд, что и точное совпадение."""
    from news.active_queue import next_active_slot_by_kind

    base = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=2)
    later = base + timedelta(hours=15)
    monkeypatch.setattr(
        "news.active_queue.build_schedule_window",
        lambda *args, **kwargs: _slots(("daily", base), ("daily", later)),
    )

    assert next_active_slot_by_kind(occupied_times=[base - timedelta(minutes=10)])["daily"] == later


def test_manual_post_far_from_slot_does_not_take_it(monkeypatch) -> None:
    """Ручной пост в двух часах от слота слот не занимает — иначе очередь
    откладывала бы свои посты без причины."""
    from news.active_queue import next_active_slot_by_kind

    base = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=3)
    monkeypatch.setattr(
        "news.active_queue.build_schedule_window",
        lambda *args, **kwargs: _slots(("daily", base), ("daily", base + timedelta(hours=15))),
    )

    assert next_active_slot_by_kind(occupied_times=[base - timedelta(hours=2)])["daily"] == base


def test_rebalance_treats_only_unmanaged_scheduled_posts_as_occupied(monkeypatch) -> None:
    """Слот занимают ручные посты; собственные посты очереди она двигает
    сама и слот ими не блокирует."""
    now_utc = datetime.now(UTC)
    manual_at = now_utc + timedelta(hours=3)
    captured: dict[str, object] = {}

    def _fake_next_slots(**kwargs):
        captured.update(kwargs)
        return {"daily": now_utc + timedelta(hours=18)}

    monkeypatch.setattr("news.active_queue.next_active_slot_by_kind", _fake_next_slots)
    client = _FakeClient(
        scheduled_rows=[
            {"id": "manual-1", "format_type": "manual_practice", "publish_at": manual_at.isoformat()},
            {"id": "daily-1", "format_type": "daily", "publish_at": (now_utc + timedelta(hours=5)).isoformat()},
        ],
        ready_rows=[],
    )

    rebalance_active_publish_queue(client)

    occupied = captured["occupied_times"]
    assert len(occupied) == 1
    assert abs(occupied[0] - manual_at) < timedelta(seconds=1)
    assert ("daily-1", {"status": "scheduled", "publish_at": (now_utc + timedelta(hours=18)).isoformat()}) in client.patched


def test_recently_due_manual_post_still_occupies_its_slot() -> None:
    """Ручной пост, время которого только что наступило, ещё не отправлен —
    публикатор забирает посты с шагом в несколько минут. Слот рядом с ним всё
    ещё занят; давно прошедшие посты — уже нет."""
    from news.active_queue import unmanaged_scheduled_times

    now_utc = datetime.now(UTC)
    rows = [
        {"format_type": "manual_practice", "publish_at": (now_utc - timedelta(minutes=5)).isoformat()},
        {"format_type": "manual_practice", "publish_at": (now_utc - timedelta(hours=5)).isoformat()},
        {"format_type": "daily", "publish_at": (now_utc + timedelta(hours=1)).isoformat()},
    ]

    times = unmanaged_scheduled_times(rows, now_utc=now_utc)

    assert len(times) == 1
