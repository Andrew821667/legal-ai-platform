"""Темп ответов помощника."""

from __future__ import annotations

import human_pace


def test_short_reply_still_waits() -> None:
    """Даже «Понял» не должно выскакивать мгновенно."""
    assert human_pace.typing_delay("Понял", jitter=False) >= human_pace.MIN_DELAY_SECONDS


def test_longer_reply_takes_longer() -> None:
    short = human_pace.typing_delay("Понял вас.", jitter=False)
    long = human_pace.typing_delay("Понял вас. " * 20, jitter=False)
    assert long > short


def test_delay_is_capped() -> None:
    """Человек ждёт в переписке — достоверность не стоит ожидания."""
    huge = human_pace.typing_delay("а" * 5000, jitter=False)
    assert huge == human_pace.MAX_DELAY_SECONDS


def test_empty_text_does_not_break() -> None:
    assert human_pace.typing_delay("", jitter=False) >= human_pace.MIN_DELAY_SECONDS
    assert human_pace.typing_delay(None, jitter=False) >= human_pace.MIN_DELAY_SECONDS


def test_jitter_varies_the_pause() -> None:
    """Одинаковые паузы сами по себе выглядят машинными."""
    values = {human_pace.typing_delay("Одна и та же реплика") for _ in range(40)}
    assert len(values) > 1


def test_typing_indicator_is_refreshed_on_long_pauses() -> None:
    """Telegram гасит «печатает» через несколько секунд."""
    chunks = human_pace.typing_chunks(10.0)
    assert sum(chunks) == 10.0
    assert all(chunk <= human_pace.TYPING_REFRESH_SECONDS for chunk in chunks)


def test_short_pause_is_a_single_chunk() -> None:
    assert human_pace.typing_chunks(2.0) == [2.0]
