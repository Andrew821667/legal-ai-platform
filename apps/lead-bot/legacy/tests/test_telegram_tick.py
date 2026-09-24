"""Бот раз в пару минут дёргает такт ядра — и не падает, если ядро молчит."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import bot as bot_module


@pytest.mark.anyio
async def test_tick_asks_the_core(monkeypatch) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(
        bot_module.admin_interface.admin_interface,
        "telegram_tick",
        lambda: calls.append(True) or {"health": {"ok": True}},
    )
    await bot_module.telegram_tick_job(SimpleNamespace())
    assert calls == [True]


@pytest.mark.anyio
async def test_core_failure_does_not_break_the_job(monkeypatch) -> None:
    def boom():
        raise ConnectionError("ядро недоступно")

    monkeypatch.setattr(bot_module.admin_interface.admin_interface, "telegram_tick", boom)
    await bot_module.telegram_tick_job(SimpleNamespace())


def test_tick_interval_has_a_floor(monkeypatch) -> None:
    from config import Config

    monkeypatch.setenv("TELEGRAM_TICK_INTERVAL_SECONDS", "5")
    assert Config().TELEGRAM_TICK_INTERVAL_SECONDS == 30
