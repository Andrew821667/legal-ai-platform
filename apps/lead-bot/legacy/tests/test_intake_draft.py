"""Черновик обращения юристу из разговора с ассистентом (handlers/intake_draft.py)."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from handlers import intake_draft


def test_draft_is_built_from_the_clients_own_messages() -> None:
    history = [
        {"role": "user", "message": "Здравствуйте"},
        {"role": "assistant", "message": "Чем помочь?"},
        {"role": "user", "message": "Работодатель не выплатил зарплату за два месяца."},
        {"role": "assistant", "message": "Понимаю. Есть трудовой договор?"},
        {"role": "user", "message": "Да, есть договор   и расчётные листки."},
    ]
    draft = intake_draft.draft_from_history(history)
    assert draft == "Здравствуйте\n\nРаботодатель не выплатил зарплату за два месяца.\n\nДа, есть договор и расчётные листки."
    assert "Понимаю" not in draft  # ответы ассистента в черновик не попадают


def test_draft_keeps_the_latest_messages_within_limits() -> None:
    history = [{"role": "user", "message": f"сообщение {i} " + "x" * 900} for i in range(10)]
    draft = intake_draft.draft_from_history(history)
    assert "сообщение 9" in draft and "сообщение 0" not in draft
    assert len(draft) <= intake_draft.MAX_CHARS + 10


def test_nda_mentions() -> None:
    assert intake_draft.mentions_nda("А где подписать NDA?")
    assert intake_draft.mentions_nda("соглашение о конфиденциальности")
    assert not intake_draft.mentions_nda("Нужна консультация по аренде")


@pytest.fixture
def world(monkeypatch):
    sent = {"replies": [], "edits": [], "submitted": []}

    async def _reply(message, text, **kwargs):
        sent["replies"].append((text, kwargs.get("reply_markup")))

    async def _edit(message, text, **kwargs):
        sent["edits"].append(text)

    async def _answer(query, **kwargs):
        return None

    async def _submit(**kwargs):
        sent["submitted"].append(kwargs)

    monkeypatch.setattr(intake_draft.utils, "safe_reply_text", _reply)
    monkeypatch.setattr(intake_draft.utils, "safe_reply_html", _reply)
    monkeypatch.setattr(intake_draft.utils, "safe_edit_text", _edit)
    monkeypatch.setattr(intake_draft.utils, "safe_answer_callback", _answer)
    from handlers import legal_help

    monkeypatch.setattr(legal_help, "submit_legal_help", _submit)
    monkeypatch.setattr(intake_draft.database.db, "get_user_by_telegram_id", lambda tg: {"id": 7, "telegram_id": tg})
    monkeypatch.setattr(
        intake_draft.database.db,
        "get_conversation_history",
        lambda user_id: [{"role": "user", "message": "Сосед затопил квартиру, управляющая компания молчит уже месяц."}],
    )
    return sent


def _update(data: str) -> SimpleNamespace:
    query = SimpleNamespace(data=data, from_user=SimpleNamespace(id=42, full_name="Анна", first_name="Анна"),
                            message=SimpleNamespace(message_id=100))
    return SimpleNamespace(callback_query=query)


@pytest.mark.asyncio
async def test_draft_is_shown_and_sent_only_after_choosing_who_needs_help(world) -> None:
    context = SimpleNamespace(user_data={})
    await intake_draft.handle_draft_callback(_update("idraft:make"), context)
    text, markup = world["replies"][0]
    assert "Сосед затопил квартиру" in text and "Черновик" in text
    assert world["submitted"] == []  # показ черновика ничего не отправляет
    buttons = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "idraft:send:individual" in buttons and "idraft:cancel" in buttons and "legal_help_start" in buttons

    await intake_draft.handle_draft_callback(_update("idraft:send:individual"), context)
    [submitted] = world["submitted"]
    assert submitted["description"].startswith("Сосед затопил квартиру")
    assert submitted["client_type"] == "individual" and submitted["entry"] == "assistant_draft"
    assert "передано юристу" in world["edits"][-1]
    # Повторное нажатие — черновика уже нет, второй раз не отправляется.
    await intake_draft.handle_draft_callback(_update("idraft:send:individual"), context)
    assert len(world["submitted"]) == 1


@pytest.mark.asyncio
async def test_expired_or_cancelled_draft_is_not_sent(world) -> None:
    context = SimpleNamespace(user_data={intake_draft.DRAFT_KEY: {"text": "старый текст обращения к юристу", "at": time.time() - 3600}})
    await intake_draft.handle_draft_callback(_update("idraft:send:company"), context)
    assert world["submitted"] == [] and "устарел" in world["replies"][-1][0]

    await intake_draft.handle_draft_callback(_update("idraft:make"), context)
    await intake_draft.handle_draft_callback(_update("idraft:cancel"), context)
    await intake_draft.handle_draft_callback(_update("idraft:send:company"), context)
    assert world["submitted"] == []


@pytest.mark.asyncio
async def test_offer_is_shown_at_most_once_a_day(world) -> None:
    context = SimpleNamespace(user_data={})
    assert await intake_draft.offer_draft(object(), context) is True
    assert await intake_draft.offer_draft(object(), context) is False
    assert len(world["replies"]) == 1
