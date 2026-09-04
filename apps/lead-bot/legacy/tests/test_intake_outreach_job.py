"""Фоновая задача первого обращения к клиенту.

Эти проверки появились после того, как задача полтора месяца молча падала в
продакшене: она обращалась к `core_api_bridge.bridge`, а модуль экспортирует
экземпляр под именем `core_api_bridge`. AttributeError возникал на первой же
строке, каждые две минуты, и ни один тест этого не видел — покрыты были
формулировки сообщения, но не сама задача.

Поэтому здесь задача вызывается целиком, с настоящим модулем моста: любая
опечатка в его имени или в имени метода снова уронит тест, а не продакшен.
"""

from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace

import pytest

import bot as bot_module
import core_api_bridge as bridge_module


def test_bridge_instance_is_reachable_by_the_name_the_job_uses() -> None:
    """Имя, под которым задача берёт мост, существует в модуле."""
    assert hasattr(bridge_module, "core_api_bridge")
    for method in (
        "list_intakes_pending_outreach",
        "mark_intake_outreach",
        "record_clarification",
        "record_intake_document",
        "get_nda_status",
        "sign_nda",
    ):
        assert hasattr(bridge_module.core_api_bridge, method), method


class _Bot:
    def __init__(self, *, fail_with: Exception | None = None) -> None:
        self.sent: list[dict] = []
        self._fail_with = fail_with

    async def send_message(self, **kwargs):
        if self._fail_with is not None:
            raise self._fail_with
        self.sent.append(kwargs)


def _context(bot: _Bot) -> SimpleNamespace:
    # В python-telegram-bot user_data — mappingproxy над defaultdict: обращение
    # по неизвестному ключу создаёт запись. Обычный dict здесь дал бы KeyError
    # и проверял бы поведение, которого в продакшене нет.
    return SimpleNamespace(
        bot=bot,
        application=SimpleNamespace(user_data=defaultdict(dict)),
    )


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Настоящий объект моста с подменёнными сетевыми методами."""
    state = SimpleNamespace(pending=[], marked=[])

    monkeypatch.setattr(bridge_module.core_api_bridge, "enabled", True, raising=False)
    monkeypatch.setattr(
        bridge_module.core_api_bridge,
        "list_intakes_pending_outreach",
        lambda **kwargs: list(state.pending),
    )
    monkeypatch.setattr(
        bridge_module.core_api_bridge,
        "mark_intake_outreach",
        lambda intake_id, blocked_reason=None: state.marked.append((intake_id, blocked_reason)),
    )
    return state


@pytest.mark.anyio
async def test_client_with_telegram_gets_the_message_and_a_dialog(bridge, monkeypatch) -> None:
    bridge.pending = [
        {
            "intake_id": "i-1",
            "lead_id": "l-1",
            "telegram_user_id": 848510279,
            "legal_area": "employment",
            "name": "Андрей",
        }
    ]
    saved: dict = {}
    monkeypatch.setattr(
        bot_module.database.db,
        "save_intake_dialog_state",
        lambda user_id, user_data: saved.update({user_id: dict(user_data)}),
    )

    bot = _Bot()
    context = _context(bot)
    await bot_module.intake_outreach_job(context)

    assert len(bot.sent) == 1
    assert bot.sent[0]["chat_id"] == 848510279
    assert bridge.marked == [("i-1", None)]

    # Диалог заведён: и в памяти процесса, и в базе.
    user_data = context.application.user_data[848510279]
    assert user_data["intake_dialog_stage"] == "asking"
    assert user_data["intake_dialog_intake_id"] == "i-1"
    assert 848510279 in saved


@pytest.mark.anyio
async def test_intake_without_telegram_is_handed_to_the_lawyer(bridge, monkeypatch) -> None:
    """Заявка не из Telegram: написать первым нельзя, юрист должен узнать."""
    bridge.pending = [
        {
            "intake_id": "i-2",
            "lead_id": "l-2",
            "telegram_user_id": None,
            "legal_area": "family_inheritance",
            "name": "Александр",
        }
    ]
    monkeypatch.setattr(bot_module.config, "ADMIN_TELEGRAM_ID", 111, raising=False)

    bot = _Bot()
    await bot_module.intake_outreach_job(_context(bot))

    assert len(bot.sent) == 1
    assert bot.sent[0]["chat_id"] == 111
    assert "НЕ УДАЛОСЬ СВЯЗАТЬСЯ" in bot.sent[0]["text"]
    # Отметка обязательна: без неё задача вернётся к обращению на следующем круге.
    assert bridge.marked == [("i-2", "no_telegram")]


@pytest.mark.anyio
async def test_blocked_bot_is_recorded_and_not_retried(bridge, monkeypatch) -> None:
    """Клиент не писал боту или заблокировал его — повторять бессмысленно."""
    from telegram.error import Forbidden

    bridge.pending = [
        {"intake_id": "i-3", "lead_id": "l-3", "telegram_user_id": 5, "legal_area": "contracts"}
    ]
    monkeypatch.setattr(bot_module.config, "ADMIN_TELEGRAM_ID", 111, raising=False)

    bot = _Bot(fail_with=Forbidden("bot was blocked by the user"))
    await bot_module.intake_outreach_job(_context(bot))

    assert bridge.marked == [("i-3", "forbidden")]


@pytest.mark.anyio
async def test_temporary_failure_leaves_the_intake_for_the_next_round(bridge, monkeypatch) -> None:
    """Сетевой сбой — не повод терять обращение: отметку не ставим."""
    bridge.pending = [
        {"intake_id": "i-4", "lead_id": "l-4", "telegram_user_id": 5, "legal_area": "contracts"}
    ]

    bot = _Bot(fail_with=TimeoutError("сеть недоступна"))
    await bot_module.intake_outreach_job(_context(bot))

    assert bridge.marked == []


@pytest.mark.anyio
async def test_disabled_bridge_does_nothing(monkeypatch) -> None:
    monkeypatch.setattr(bridge_module.core_api_bridge, "enabled", False, raising=False)
    bot = _Bot()
    await bot_module.intake_outreach_job(_context(bot))
    assert bot.sent == []
