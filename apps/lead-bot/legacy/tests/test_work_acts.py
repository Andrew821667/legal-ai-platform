from __future__ import annotations

from types import SimpleNamespace

import pytest
from handlers import work_acts as flow


class Bot:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return SimpleNamespace(message_id=900)


@pytest.fixture
def replies(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    sent: list[str] = []

    async def reply(message, text, **kwargs) -> None:
        sent.append(text)

    async def answer(query, **kwargs) -> None:
        return None

    monkeypatch.setattr(flow.utils, "safe_reply_text", reply)
    monkeypatch.setattr(flow.utils, "safe_answer_callback", answer)
    return sent


def _agreement(**overrides) -> dict:
    data = {
        "id": "11111111-1111-1111-1111-111111111111",
        "agreement_number": "AV-20260909-ABC123",
        "status": "signed",
        "subject": "Сопровождение раздела имущества",
        "scope_text": "Подготовка соглашения, сопровождение у нотариуса",
        "amount_minor": 8_000_000,
    }
    data.update(overrides)
    return data


def _act(**overrides) -> dict:
    data = {
        "id": "22222222-2222-2222-2222-222222222222",
        "act_number": "AC-20260911-XYZ789",
        "agreement_id": "11111111-1111-1111-1111-111111111111",
        "status": "draft",
        "description_text": "Подготовлено и подано заявление.",
        "amount_minor": 8_000_000,
    }
    data.update(overrides)
    return data


def test_format_rub_matches_the_web_formatter() -> None:
    assert flow.format_rub(8_000_000) == "80 000 ₽"
    assert flow.format_rub(1250050) == "12 500,50 ₽"


@pytest.mark.anyio
async def test_wizard_creates_a_draft_act_with_defaults(monkeypatch, replies) -> None:
    """«-» на обоих шагах — акт уходит с текстом и суммой договора как есть."""
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    message = SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID)
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
    )
    created: list[dict] = []

    def create(**kwargs):
        created.append(kwargs)
        return _act()

    monkeypatch.setattr(flow.admin_interface.admin_interface, "create_work_act", create)

    await flow.start_act_wizard(message, ctx, _agreement())
    assert any("По умолчанию" in text for text in replies)

    assert await flow.handle_message(update, ctx, "-")
    assert await flow.handle_message(update, ctx, "-")

    assert flow.STATE_KEY not in ctx.user_data
    assert created == [
        {
            "agreement_id": "11111111-1111-1111-1111-111111111111",
            "description_text": "Подготовка соглашения, сопровождение у нотариуса",
            "amount_minor": 8_000_000,
            "prepared_by_telegram_user_id": flow.config.ADMIN_TELEGRAM_ID,
        }
    ]
    assert any("AC-20260911-XYZ789" in text for text in replies)


@pytest.mark.anyio
async def test_draft_act_offers_a_send_button(monkeypatch) -> None:
    """Кнопка ведёт ровно на этот акт — не на предыдущий и не в никуда."""
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    message = SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID)
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
    )
    captured: dict = {}

    async def reply(msg, text, **kwargs) -> None:
        captured.update(text=text, **kwargs)

    monkeypatch.setattr(flow.utils, "safe_reply_text", reply)
    monkeypatch.setattr(flow.admin_interface.admin_interface, "create_work_act", lambda **kwargs: _act())

    await flow.start_act_wizard(message, ctx, _agreement())
    await flow.handle_message(update, ctx, "-")
    await flow.handle_message(update, ctx, "-")

    (button,) = [b for row in captured["reply_markup"].inline_keyboard for b in row]
    assert button.text == "Отправить клиенту"
    assert button.callback_data == "act_a:send:22222222-2222-2222-2222-222222222222"


@pytest.mark.anyio
async def test_sent_act_offers_a_mark_paid_button(monkeypatch) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    query = SimpleNamespace(
        data="act_a:send:22222222-2222-2222-2222-222222222222",
        from_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
        message=SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID),
    )
    update = SimpleNamespace(callback_query=query)
    captured: dict = {}

    async def reply(msg, text, **kwargs) -> None:
        captured.update(text=text, **kwargs)

    async def answer(query, **kwargs) -> None:
        return None

    monkeypatch.setattr(flow.utils, "safe_reply_text", reply)
    monkeypatch.setattr(flow.utils, "safe_answer_callback", answer)
    monkeypatch.setattr(
        flow.admin_interface.admin_interface, "send_work_act", lambda *_: _act(status="sent")
    )

    await flow.handle_admin_callback(update, ctx)

    (button,) = [b for row in captured["reply_markup"].inline_keyboard for b in row]
    assert button.text == "Отметить оплаченным"
    assert button.callback_data == "act_a:paid:22222222-2222-2222-2222-222222222222"


@pytest.mark.anyio
async def test_wizard_accepts_custom_values(monkeypatch, replies) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    message = SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID)
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
    )
    created: list[dict] = []
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "create_work_act",
        lambda **kwargs: created.append(kwargs) or _act(),
    )

    await flow.start_act_wizard(message, ctx, _agreement())
    assert await flow.handle_message(update, ctx, "Составлено дополнительное соглашение.")
    assert await flow.handle_message(update, ctx, "12 500,50")

    assert created[0]["description_text"] == "Составлено дополнительное соглашение."
    assert created[0]["amount_minor"] == 1_250_050


@pytest.mark.anyio
async def test_wizard_rejects_an_unparsable_amount(monkeypatch, replies) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    message = SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID)
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
    )
    calls: list[dict] = []
    monkeypatch.setattr(
        flow.admin_interface.admin_interface, "create_work_act", lambda **kwargs: calls.append(kwargs)
    )

    await flow.start_act_wizard(message, ctx, _agreement())
    await flow.handle_message(update, ctx, "-")
    assert await flow.handle_message(update, ctx, "много денег")

    assert calls == []
    assert ctx.user_data.get(flow.STATE_KEY) == "act_wizard"
    assert any("число в рублях" in text for text in replies)


@pytest.mark.anyio
async def test_wizard_cancel_clears_state(replies) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    message = SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID)
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
    )
    await flow.start_act_wizard(message, ctx, _agreement())
    assert await flow.handle_message(update, ctx, "/cancel")
    assert flow.STATE_KEY not in ctx.user_data


@pytest.mark.anyio
async def test_wizard_ignores_messages_from_a_non_admin() -> None:
    ctx = SimpleNamespace(user_data={flow.STATE_KEY: "act_wizard"}, bot=Bot())
    update = SimpleNamespace(
        effective_message=SimpleNamespace(chat_id=999),
        effective_user=SimpleNamespace(id=999),
    )
    assert not await flow.handle_message(update, ctx, "текст")


@pytest.mark.anyio
async def test_new_act_requires_a_signed_agreement(monkeypatch, replies) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    query = SimpleNamespace(
        data="act_a:new:11111111-1111-1111-1111-111111111111",
        from_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
        message=SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID),
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "get_service_agreement",
        lambda *_: _agreement(status="sent"),
    )

    await flow.handle_admin_callback(update, ctx)

    assert flow.STATE_KEY not in ctx.user_data
    assert any("только по подписанному" in text for text in replies)


@pytest.mark.anyio
async def test_send_button_confirms_and_offers_paid_button(monkeypatch, replies) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    query = SimpleNamespace(
        data="act_a:send:22222222-2222-2222-2222-222222222222",
        from_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
        message=SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID),
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(
        flow.admin_interface.admin_interface, "send_work_act", lambda *_: _act(status="sent")
    )

    await flow.handle_admin_callback(update, ctx)

    assert any("отправлен клиенту" in text for text in replies)


@pytest.mark.anyio
async def test_send_button_failure_shows_a_reason(monkeypatch, replies) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    query = SimpleNamespace(
        data="act_a:send:22222222-2222-2222-2222-222222222222",
        from_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
        message=SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID),
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(flow.admin_interface.admin_interface, "send_work_act", lambda *_: None)

    await flow.handle_admin_callback(update, ctx)

    assert any("не удалось" in text for text in replies)


@pytest.mark.anyio
async def test_paid_button_marks_the_act_paid(monkeypatch, replies) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    query = SimpleNamespace(
        data="act_a:paid:22222222-2222-2222-2222-222222222222",
        from_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
        message=SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID),
    )
    update = SimpleNamespace(callback_query=query)
    calls: list[dict] = []

    def mark(act_id, **kwargs):
        calls.append({"act_id": act_id, **kwargs})
        return _act(status="paid")

    monkeypatch.setattr(flow.admin_interface.admin_interface, "mark_work_act_paid", mark)

    await flow.handle_admin_callback(update, ctx)

    assert calls == [
        {"act_id": "22222222-2222-2222-2222-222222222222", "paid_by_telegram_user_id": flow.config.ADMIN_TELEGRAM_ID}
    ]
    assert any("отмечен оплаченным" in text for text in replies)


@pytest.mark.anyio
async def test_admin_callback_ignores_a_stranger(replies) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    query = SimpleNamespace(
        data="act_a:paid:22222222-2222-2222-2222-222222222222",
        from_user=SimpleNamespace(id=999999),
        message=SimpleNamespace(chat_id=999999),
    )
    update = SimpleNamespace(callback_query=query)
    # Не должно упасть и не должно ничего вызвать — просто игнор.
    await flow.handle_admin_callback(update, ctx)


@pytest.mark.anyio
async def test_client_claim_notifies_the_admin(monkeypatch, replies) -> None:
    bot = Bot()
    ctx = SimpleNamespace(user_data={}, bot=bot)
    query = SimpleNamespace(
        data="act_c:claim:22222222-2222-2222-2222-222222222222",
        from_user=SimpleNamespace(id=5150),
        message=SimpleNamespace(chat_id=5150),
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "claim_work_act_paid",
        lambda act_id, **kwargs: _act(status="claimed_paid"),
    )

    await flow.handle_client_callback(update, ctx)

    assert any("Юрист проверит" in text for text in replies)
    assert len(bot.messages) == 1
    assert bot.messages[0]["chat_id"] == flow.config.ADMIN_TELEGRAM_ID
    assert "AC-20260911-XYZ789" in bot.messages[0]["text"]


@pytest.mark.anyio
async def test_client_claim_failure_is_generic(monkeypatch, replies) -> None:
    """403/409 от ядра — общее сообщение, не техническая деталь ответа."""
    bot = Bot()
    ctx = SimpleNamespace(user_data={}, bot=bot)
    query = SimpleNamespace(
        data="act_c:claim:22222222-2222-2222-2222-222222222222",
        from_user=SimpleNamespace(id=999999),
        message=SimpleNamespace(chat_id=999999),
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(
        flow.admin_interface.admin_interface, "claim_work_act_paid", lambda *args, **kwargs: None
    )

    await flow.handle_client_callback(update, ctx)

    assert any("Не получилось отметить оплату" in text for text in replies)
    assert bot.messages == []
