from __future__ import annotations

from news.publish_loop import _idle_fallback_allowed


def test_idle_fallback_is_blocked_during_startup_grace() -> None:
    assert _idle_fallback_allowed(started_at=100.0, now_ts=699.0, grace_seconds=600) is False


def test_idle_fallback_is_allowed_after_startup_grace() -> None:
    assert _idle_fallback_allowed(started_at=100.0, now_ts=700.0, grace_seconds=600) is True


def test_idle_fallback_grace_can_be_disabled() -> None:
    assert _idle_fallback_allowed(started_at=100.0, now_ts=100.0, grace_seconds=0) is True
