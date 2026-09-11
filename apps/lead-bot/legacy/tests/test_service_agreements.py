from __future__ import annotations

from types import SimpleNamespace

import pytest
from handlers import service_agreements as flow


class Bot:
    def __init__(self) -> None:
        self.documents: list[dict] = []
        self.messages: list[dict] = []

    async def send_document(self, **kwargs):
        self.documents.append(kwargs)
        return SimpleNamespace(message_id=501)

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return SimpleNamespace(message_id=502, delete=_noop)


async def _noop() -> None:
    return None


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


def _agreement(
    status: str = "viewed",
    *,
    company: bool = False,
    details_complete: bool = True,
) -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "agreement_number": "AV-20260907-ABC123",
        "intake_id": "22222222-2222-2222-2222-222222222222",
        "status": status,
        "subject": "Проверка договора поставки",
        "price_text": "15 000 рублей",
        "payment_terms": "100% до начала работы",
        "client_org": "ООО «Пример»" if company else None,
        "client_type": "organization" if company else "person",
        "client_details_complete": details_complete,
        "client_position": "Генеральный директор" if company else None,
        "client_authority_basis": "Устав" if company else None,
        "client_telegram_user_id": 77,
        "hash": "a" * 64,
        "text": "Точный текст договора",
    }


@pytest.mark.anyio
async def test_admin_wizard_creates_preview_in_admin_bot(monkeypatch, replies) -> None:
    bot = Bot()
    ctx = SimpleNamespace(user_data={}, bot=bot)
    message = SimpleNamespace(chat_id=42)
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
    )
    created: list[dict] = []

    def create(payload, key):
        created.append({"payload": payload, "key": key})
        return _agreement("draft")

    monkeypatch.setattr(flow.admin_interface.admin_interface, "create_service_agreement", create)
    intake = {
        "id": "22222222-2222-2222-2222-222222222222",
        "lead_id": "33333333-3333-3333-3333-333333333333",
        "telegram_user_id": 77,
    }
    await flow._start_wizard(message, ctx, intake)
    for value in (
        "Проверка договора поставки",
        "Изучить договор и дать замечания",
        "Судебное представительство",
        "Три рабочих дня",
        "15 000 рублей",
        "100% до начала работы",
    ):
        assert await flow.handle_message(update, ctx, value)

    assert len(created) == 1
    assert created[0]["payload"]["intake_id"] == intake["id"]
    assert created[0]["payload"]["prepared_by_telegram_user_id"] == flow.config.ADMIN_TELEGRAM_ID
    assert bot.documents
    assert flow.STATE_KEY not in ctx.user_data


@pytest.mark.anyio
async def test_admin_nda_request_is_bound_to_the_core_lead(monkeypatch, replies) -> None:
    bot = Bot()
    ctx = SimpleNamespace(user_data={}, bot=bot)
    intake_id = "22222222-2222-2222-2222-222222222222"
    lead_id = "33333333-3333-3333-3333-333333333333"
    query = SimpleNamespace(
        data=f"sa_a:nda:{intake_id}",
        from_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
        message=SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID),
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "get_legal_intake",
        lambda value: {
            "id": value,
            "lead_id": lead_id,
            "telegram_user_id": 77,
        },
    )

    await flow.handle_admin_callback(update, ctx)

    assert bot.messages[0]["chat_id"] == 77
    button = bot.messages[0]["reply_markup"].inline_keyboard[0][0]
    assert button.callback_data == f"nda:open:{lead_id}"
    assert replies[-1] == "Запрос на подписание NDA отправлен клиенту."


@pytest.mark.anyio
async def test_admin_can_close_intake_without_agreement(monkeypatch, replies) -> None:
    intake_id = "22222222-2222-2222-2222-222222222222"
    query = SimpleNamespace(
        data=f"sa_a:noneok:{intake_id}",
        from_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
        message=SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID),
    )
    update = SimpleNamespace(callback_query=query)
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    saved: list[dict] = []
    shown: list[str] = []

    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "get_legal_intake",
        lambda value: {"id": value, "internal_note": "Клиенту ответили."},
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "list_service_agreements_for_intake",
        lambda value: [],
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "update_legal_intake",
        lambda value, payload: saved.append({"id": value, **payload}) or payload,
    )

    async def show(message, value) -> None:
        shown.append(value)

    monkeypatch.setattr(flow, "_show_intake", show)

    await flow.handle_admin_callback(update, ctx)

    assert saved[0]["status"] == "closed"
    assert "без заключения договора/соглашения" in saved[0]["internal_note"]
    assert shown == [intake_id]


@pytest.mark.anyio
async def test_admin_cannot_close_intake_with_existing_agreement(monkeypatch, replies) -> None:
    intake_id = "22222222-2222-2222-2222-222222222222"
    query = SimpleNamespace(
        data=f"sa_a:noneok:{intake_id}",
        from_user=SimpleNamespace(id=flow.config.ADMIN_TELEGRAM_ID),
        message=SimpleNamespace(chat_id=flow.config.ADMIN_TELEGRAM_ID),
    )
    update = SimpleNamespace(callback_query=query)
    ctx = SimpleNamespace(user_data={}, bot=Bot())

    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "get_legal_intake",
        lambda value: {"id": value},
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "list_service_agreements_for_intake",
        lambda value: [_agreement("draft")],
    )

    await flow.handle_admin_callback(update, ctx)

    assert "уже создан договор" in replies[-1]


@pytest.mark.anyio
async def test_intake_card_offers_close_without_agreement(monkeypatch) -> None:
    intake_id = "22222222-2222-2222-2222-222222222222"
    captured: dict = {}

    async def reply(message, text, **kwargs) -> None:
        captured.update(text=text, **kwargs)

    monkeypatch.setattr(flow.utils, "safe_reply_text", reply)
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "get_legal_intake",
        lambda value: {
            "id": value,
            "lead_id": "33333333-3333-3333-3333-333333333333",
            "lead_name": "Александр Рябов",
            "status": "scope_preparation",
            "conflict_status": "clear",
            "description": "Юридическая помощь",
        },
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "list_service_agreements_for_intake",
        lambda value: [],
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "get_nda_status",
        lambda value: {"signed": True},
    )

    await flow._show_intake(SimpleNamespace(chat_id=1), intake_id)

    buttons = [button for row in captured["reply_markup"].inline_keyboard for button in row]
    option = next(
        button for button in buttons if button.text == "Без заключения договора/соглашения"
    )
    assert option.callback_data == f"sa_a:none:{intake_id}"


@pytest.mark.anyio
async def test_signed_agreement_offers_the_act_button_and_lists_acts(monkeypatch) -> None:
    """Кнопка «Выставить акт» — только у подписанного договора; черновики и
    отправленные-непросмотренные её не получают, выставлять счёт не за что."""
    intake_id = "22222222-2222-2222-2222-222222222222"
    captured: dict = {}

    async def reply(message, text, **kwargs) -> None:
        captured.update(text=text, **kwargs)

    monkeypatch.setattr(flow.utils, "safe_reply_text", reply)
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "get_legal_intake",
        lambda value: {
            "id": value,
            "lead_id": "33333333-3333-3333-3333-333333333333",
            "lead_name": "Александр Рябов",
            "status": "accepted",
            "conflict_status": "clear",
            "description": "Раздел имущества",
        },
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "list_service_agreements_for_intake",
        lambda value: [_agreement("signed")],
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface, "get_nda_status", lambda value: {"signed": True}
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface, "list_service_agreement_messages", lambda value: []
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "list_work_acts_for_agreement",
        lambda value: [
            {"act_number": "AC-20260911-ONE", "status": "paid", "amount_minor": 8_000_000}
        ],
    )

    await flow._show_intake(SimpleNamespace(chat_id=1), intake_id)

    assert "AC-20260911-ONE" in captured["text"]
    assert "оплачен" in captured["text"]
    buttons = [button for row in captured["reply_markup"].inline_keyboard for button in row]
    option = next(button for button in buttons if button.text == "Выставить акт")
    assert option.callback_data == "act_a:new:11111111-1111-1111-1111-111111111111"


@pytest.mark.anyio
async def test_unsigned_agreement_has_no_act_button(monkeypatch) -> None:
    intake_id = "22222222-2222-2222-2222-222222222222"
    captured: dict = {}

    async def reply(message, text, **kwargs) -> None:
        captured.update(text=text, **kwargs)

    monkeypatch.setattr(flow.utils, "safe_reply_text", reply)
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "get_legal_intake",
        lambda value: {
            "id": value,
            "lead_id": "33333333-3333-3333-3333-333333333333",
            "lead_name": "Александр Рябов",
            "status": "accepted",
            "conflict_status": "clear",
            "description": "Раздел имущества",
        },
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "list_service_agreements_for_intake",
        lambda value: [_agreement("sent")],
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface, "get_nda_status", lambda value: {"signed": True}
    )
    monkeypatch.setattr(
        flow.admin_interface.admin_interface, "list_service_agreement_messages", lambda value: []
    )
    called: list[str] = []
    monkeypatch.setattr(
        flow.admin_interface.admin_interface,
        "list_work_acts_for_agreement",
        lambda value: called.append(value) or [],
    )

    await flow._show_intake(SimpleNamespace(chat_id=1), intake_id)

    buttons = [button for row in captured["reply_markup"].inline_keyboard for button in row]
    assert not any(button.text == "Выставить акт" for button in buttons)
    # Ненужный поход в ядро за актами договора, который не подписан.
    assert called == []


@pytest.mark.anyio
async def test_client_must_open_document_before_signing(monkeypatch, replies) -> None:
    bot = Bot()
    ctx = SimpleNamespace(user_data={}, bot=bot)
    message = SimpleNamespace(chat_id=77)
    user = SimpleNamespace(id=77, username="client")
    query = SimpleNamespace(
        data="sa_c:sign:11111111-1111-1111-1111-111111111111",
        from_user=user,
        message=message,
        id="callback-1",
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(
        flow.core_api_bridge, "get_service_agreement", lambda *args: _agreement("sent")
    )

    await flow.handle_client_callback(update, ctx)

    assert any("Сначала откройте" in text for text in replies)
    assert flow.STATE_KEY not in ctx.user_data


@pytest.mark.anyio
async def test_client_open_records_exact_hash(monkeypatch, replies) -> None:
    bot = Bot()
    ctx = SimpleNamespace(user_data={}, bot=bot)
    message = SimpleNamespace(chat_id=77)
    user = SimpleNamespace(id=77, username="client")
    query = SimpleNamespace(
        data="sa_c:open:11111111-1111-1111-1111-111111111111",
        from_user=user,
        message=message,
        id="callback-2",
    )
    update = SimpleNamespace(callback_query=query)
    viewed: list[dict] = []
    monkeypatch.setattr(
        flow.core_api_bridge, "get_service_agreement", lambda *args: _agreement("sent")
    )

    def mark(agreement_id, **kwargs):
        viewed.append({"id": agreement_id, **kwargs})
        return _agreement("viewed")

    monkeypatch.setattr(flow.core_api_bridge, "mark_service_agreement_viewed", mark)
    await flow.handle_client_callback(update, ctx)

    assert bot.documents
    assert viewed[0]["document_hash"] == "a" * 64
    assert viewed[0]["message_id"] == 501
    assert viewed[0]["callback_id"] == "callback-2"


@pytest.mark.anyio
async def test_client_open_requires_details_before_document(monkeypatch, replies) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    query = SimpleNamespace(
        data="sa_c:open:11111111-1111-1111-1111-111111111111",
        from_user=SimpleNamespace(id=77, username="client"),
        message=SimpleNamespace(chat_id=77),
        id="callback-details",
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(
        flow.core_api_bridge,
        "get_service_agreement",
        lambda *args: _agreement("sent", details_complete=False),
    )

    await flow.handle_client_callback(update, ctx)

    assert "заполните реквизиты" in replies[-1].lower()


@pytest.mark.anyio
async def test_client_details_create_and_open_signable_revision(monkeypatch, replies) -> None:
    bot = Bot()
    ctx = SimpleNamespace(user_data={}, bot=bot)
    message = SimpleNamespace(chat_id=77)
    user = SimpleNamespace(id=77, username="client")
    query = SimpleNamespace(
        data="sa_c:person:11111111-1111-1111-1111-111111111111",
        from_user=user,
        message=message,
        id="callback-person",
    )
    update = SimpleNamespace(callback_query=query)
    captured: dict = {}
    revised = _agreement("sent")
    revised["id"] = "44444444-4444-4444-4444-444444444444"
    revised["agreement_number"] = "AV-20260907-ABC123-R2"

    monkeypatch.setattr(
        flow.core_api_bridge,
        "get_service_agreement",
        lambda *args: _agreement("sent", details_complete=False),
    )

    def complete(agreement_id, payload):
        captured.update(source_id=agreement_id, payload=payload)
        return revised

    def mark(agreement_id, **kwargs):
        captured.update(viewed_id=agreement_id, viewed=kwargs)
        return {**revised, "status": "viewed"}

    monkeypatch.setattr(
        flow.core_api_bridge,
        "complete_service_agreement_client_details",
        complete,
    )
    monkeypatch.setattr(flow.core_api_bridge, "mark_service_agreement_viewed", mark)

    await flow.handle_client_callback(update, ctx)
    input_update = SimpleNamespace(effective_message=message, effective_user=user)
    for value in (
        "Петров Пётр Петрович",
        "+7 900 000-00-00",
        "г. Москва, ул. Тестовая, д. 1",
        "паспорт 00 00 000000, выдан 01.01.2020",
    ):
        assert await flow.handle_message(input_update, ctx, value)

    assert captured["payload"]["telegram_user_id"] == 77
    assert captured["payload"]["identity_document"].startswith("паспорт")
    assert captured["viewed_id"] == revised["id"]
    assert captured["viewed"]["document_hash"] == "a" * 64
    assert bot.documents
    assert flow.STATE_KEY not in ctx.user_data


@pytest.mark.anyio
async def test_client_details_survive_document_delivery_failure(monkeypatch, replies) -> None:
    ctx = SimpleNamespace(
        user_data={
            flow.STATE_KEY: "client_details",
            flow.DATA_KEY: {
                "agreement_id": "11111111-1111-1111-1111-111111111111",
                "client_type": "person",
                "field_index": 3,
                "full_name": "Петров Пётр Петрович",
                "contact": "+7 900 000-00-00",
                "address": "г. Москва, ул. Тестовая, д. 1",
            },
        },
        bot=Bot(),
    )
    message = SimpleNamespace(chat_id=77)
    update = SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=77, username="client"),
    )
    monkeypatch.setattr(
        flow.core_api_bridge,
        "complete_service_agreement_client_details",
        lambda *args: _agreement("sent"),
    )

    async def fail(*args, **kwargs):
        raise flow.TelegramError("delivery failed")

    monkeypatch.setattr(flow, "_send_document", fail)

    assert await flow.handle_message(
        update,
        ctx,
        "паспорт 00 00 000000, выдан 01.01.2020",
    )

    assert flow.STATE_KEY not in ctx.user_data
    assert "Реквизиты сохранены" in replies[-1]


@pytest.mark.anyio
async def test_company_signer_uses_stored_authority(monkeypatch, replies) -> None:
    bot = Bot()
    ctx = SimpleNamespace(user_data={}, bot=bot)
    message = SimpleNamespace(chat_id=77)
    user = SimpleNamespace(id=77, username="client")
    query = SimpleNamespace(
        data="sa_c:sign:11111111-1111-1111-1111-111111111111",
        from_user=user,
        message=message,
        id="callback-3",
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(
        flow.core_api_bridge, "get_service_agreement", lambda *args: _agreement(company=True)
    )

    await flow.handle_client_callback(update, ctx)
    assert ctx.user_data[flow.STATE_KEY] == "client_confirm"
    assert ctx.user_data[flow.DATA_KEY]["signer_position"] == "Генеральный директор"
    assert ctx.user_data[flow.DATA_KEY]["authority_basis"] == "Устав"


@pytest.mark.anyio
async def test_already_signed_message_is_sent_once(monkeypatch, replies) -> None:
    ctx = SimpleNamespace(user_data={}, bot=Bot())
    query = SimpleNamespace(
        data="sa_c:sign:11111111-1111-1111-1111-111111111111",
        from_user=SimpleNamespace(id=77, username="client"),
        message=SimpleNamespace(chat_id=77),
        id="callback-4",
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(
        flow.core_api_bridge,
        "get_service_agreement",
        lambda *args: _agreement("signed"),
    )

    await flow.handle_client_callback(update, ctx)

    assert replies == ["Этот договор уже подписан."]


@pytest.mark.anyio
async def test_client_question_notice_opens_the_card_directly(replies, monkeypatch) -> None:
    """Самое частое действие юриста — ответить на вопрос клиента.

    Раньше уведомление вело только в старый диалог с ботом, а из рабочего
    места до нужной карточки надо было добираться через список. Теперь первая
    кнопка — сразу карточка этого клиента; старый путь остаётся рядом.
    """
    bot = Bot()
    agreement = {**_agreement("sent"), "lead_id": "33333333-3333-3333-3333-333333333333"}
    monkeypatch.setattr(
        flow.core_api_bridge, "add_service_agreement_question", lambda *a, **k: {"ok": True}
    )
    monkeypatch.setattr(flow.core_api_bridge, "get_service_agreement", lambda *a, **k: agreement)
    monkeypatch.setattr(
        flow.get_config(), "LAWYER_WORKSPACE_URL", "https://example.ru/lawyer", raising=False
    )
    context = SimpleNamespace(
        bot=bot,
        user_data={
            flow.STATE_KEY: "client_question",
            flow.DATA_KEY: {"agreement_id": agreement["id"]},
        },
    )
    update = SimpleNamespace(
        effective_message=SimpleNamespace(chat_id=7),
        effective_user=SimpleNamespace(id=7),
    )

    handled = await flow.handle_message(update, context, "А что с нотариусом?")

    assert handled
    notice = bot.messages[0]
    assert "А что с нотариусом?" in notice["text"]
    rows = notice["reply_markup"].inline_keyboard
    assert rows[0][0].web_app.url == "https://example.ru/lawyer?client=33333333-3333-3333-3333-333333333333"
    assert rows[1][0].callback_data == f"sa_a:reply:{agreement['id']}"
