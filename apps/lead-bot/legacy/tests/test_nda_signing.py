"""Сценарий подписания соглашения о конфиденциальности.

Проверяется то, ради чего клиент вводит данные: подпись, за которой стоит
только идентификатор аккаунта, при споре почти ничего не доказывает.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import nda_signing as nda


@pytest.fixture
def replies(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    sent: list[str] = []

    async def _reply(message, text, **kwargs) -> None:
        sent.append(text)

    async def _answer(query, **kwargs) -> None:
        return None

    monkeypatch.setattr(nda.utils, "safe_reply_text", _reply)
    monkeypatch.setattr(nda.utils, "safe_answer_callback", _answer)
    return sent


@pytest.fixture
def context() -> SimpleNamespace:
    return SimpleNamespace(user_data={nda.LEAD_KEY: "lead-1"})


@pytest.fixture
def update() -> SimpleNamespace:
    message = SimpleNamespace(chat=SimpleNamespace(id=42))
    return SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=42, username="client", full_name="Иван П"),
        callback_query=None,
    )


def _bridge(monkeypatch: pytest.MonkeyPatch, **overrides) -> dict:
    calls: dict = {}

    def _status(lead_id, **kwargs):
        calls["status"] = {"lead_id": lead_id, **kwargs}
        return overrides.get("status")

    def _sign(**kwargs):
        calls["sign"] = kwargs
        return overrides.get("sign_result", {"signed": True, "already_signed": False})

    monkeypatch.setattr(nda.core_api_bridge, "get_nda_status", _status)
    monkeypatch.setattr(
        nda.core_api_bridge,
        "get_nda_context_by_telegram",
        lambda telegram_user_id: overrides.get("telegram_context"),
    )
    monkeypatch.setattr(
        nda.core_api_bridge,
        "get_nda_document",
        lambda: overrides.get("document", {"text": "текст соглашения", "hash": "abc"}),
    )
    monkeypatch.setattr(nda.core_api_bridge, "sign_nda", _sign)
    return calls


def _press(update, context, action: str):
    update.callback_query = SimpleNamespace(
        data=f"nda:{action}", message=update.effective_message
    )
    return nda.handle_callback(update, context)


# --- проверки формулировок и разбора ввода -------------------------------


def test_full_name_needs_at_least_two_parts() -> None:
    assert nda.looks_like_full_name("Иванов Иван Иванович")
    assert nda.looks_like_full_name("Ли Сюань")
    assert not nda.looks_like_full_name("Иван")
    assert not nda.looks_like_full_name("да")
    assert not nda.looks_like_full_name("")


def test_contact_accepts_phone_or_email() -> None:
    assert nda.looks_like_contact("+7 900 123-45-67")
    assert nda.looks_like_contact("89001234567")
    assert nda.looks_like_contact("ivan@example.ru")
    assert not nda.looks_like_contact("потом скажу")
    assert not nda.looks_like_contact("12345")


def test_signing_for_self_is_recognised() -> None:
    for answer in ("от себя", "От себя лично", "физлицо", "нет", "-", ""):
        assert nda.is_signing_for_self(answer), answer
    assert not nda.is_signing_for_self('ООО "Ромашка", ИНН 7701234567')


def test_intro_explains_what_will_be_recorded() -> None:
    text = nda.build_intro(signed=False, status=None)
    assert "ФИО" in text
    assert "контакт" in text.lower()
    # Обещание простоты должно оставаться честным.
    assert "минуту" in text


def test_intro_for_signed_shows_who_signed() -> None:
    text = nda.build_intro(
        signed=True,
        status={
            "signed_at": "2026-09-05T12:00:00+03:00",
            "signer_full_name": "Иванов Иван Иванович",
            "signer_org": 'ООО "Ромашка"',
        },
    )
    assert "уже подписано" in text
    assert "Иванов Иван Иванович" in text
    assert "Ромашка" in text
    assert "2026-09-05" in text


def test_summary_shows_everything_before_signing() -> None:
    """Человек должен видеть, что именно подписывает."""
    text = nda.build_summary(
        {
            "signer_full_name": "Иванов Иван Иванович",
            "signer_contact": "+7 900 123-45-67",
            "signer_org": 'ООО "Ромашка"',
        }
    )
    assert "Иванов Иван Иванович" in text
    assert "+7 900 123-45-67" in text
    assert "Ромашка" in text
    assert "электронная подпись" in text


def test_summary_without_org_says_it_plainly() -> None:
    text = nda.build_summary({"signer_full_name": "Иванов Иван", "signer_contact": "a@b.ru"})
    assert "от себя лично" in text


# --- сценарий ------------------------------------------------------------


@pytest.mark.anyio
async def test_already_signed_is_not_offered_again(update, context, replies, monkeypatch) -> None:
    """Повторное предложение подписать читалось бы как недоверие."""
    _bridge(monkeypatch, status={"signed": True, "signed_at": "2026-09-05T10:00:00+03:00"})

    await nda.open_signing(update, context)

    assert "уже подписано" in replies[-1]
    assert nda.STAGE_KEY not in context.user_data


@pytest.mark.anyio
async def test_without_a_case_signing_is_explained_not_hidden(update, replies, monkeypatch) -> None:
    """Соглашение привязывается к делу. Молча показывать кнопку было бы обманом."""
    _bridge(monkeypatch, status=None)
    monkeypatch.setattr(nda.database.db, "get_user_by_telegram_id", lambda tid: None)
    context = SimpleNamespace(user_data={})

    await nda.open_signing(update, context)

    assert "оставить обращение" in replies[-1]


@pytest.mark.anyio
async def test_bound_case_opens_without_local_lead(update, replies, monkeypatch) -> None:
    lead_id = "33333333-3333-3333-3333-333333333333"
    calls = _bridge(monkeypatch, status={"signed": False})
    monkeypatch.setattr(nda.database.db, "get_user_by_telegram_id", lambda tid: None)
    context = SimpleNamespace(user_data={})

    await _press(update, context, f"open:{lead_id}")

    assert context.user_data[nda.LEAD_KEY] == lead_id
    assert calls["status"] == {"lead_id": lead_id, "telegram_user_id": 42}
    assert "Соглашение о конфиденциальности" in replies[-1]


@pytest.mark.anyio
async def test_menu_recovers_case_from_core_api(update, replies, monkeypatch) -> None:
    lead_id = "33333333-3333-3333-3333-333333333333"
    _bridge(
        monkeypatch,
        telegram_context={"lead_id": lead_id, "signed": False},
    )
    monkeypatch.setattr(nda.database.db, "get_user_by_telegram_id", lambda tid: None)
    context = SimpleNamespace(user_data={})

    await nda.open_signing(update, context)

    assert context.user_data[nda.LEAD_KEY] == lead_id
    assert "Соглашение о конфиденциальности" in replies[-1]


@pytest.mark.anyio
async def test_full_path_collects_details_and_signs(update, context, replies, monkeypatch) -> None:
    calls = _bridge(monkeypatch, status={"signed": False})

    await nda.open_signing(update, context)
    await _press(update, context, "begin")
    await nda.handle_message(update, context, "Иванов Иван Иванович")
    await nda.handle_message(update, context, "+7 900 123-45-67")
    await nda.handle_message(update, context, 'ООО "Ромашка", ИНН 7701234567')
    await _press(update, context, "confirm")

    signed = calls["sign"]
    assert signed["signer_full_name"] == "Иванов Иван Иванович"
    assert signed["signer_contact"] == "+7 900 123-45-67"
    assert "Ромашка" in signed["signer_org"]
    assert signed["telegram_user_id"] == 42
    assert "подписано" in replies[-1].lower()
    # Состояние сценария убрано — повторные сообщения в него не попадут.
    assert nda.STAGE_KEY not in context.user_data


@pytest.mark.anyio
async def test_signing_for_self_leaves_organization_empty(
    update, context, replies, monkeypatch
) -> None:
    calls = _bridge(monkeypatch, status={"signed": False})

    await nda.open_signing(update, context)
    await _press(update, context, "begin")
    await nda.handle_message(update, context, "Иванов Иван Иванович")
    await nda.handle_message(update, context, "ivan@example.ru")
    await nda.handle_message(update, context, "от себя")
    await _press(update, context, "confirm")

    assert calls["sign"]["signer_org"] is None


@pytest.mark.anyio
async def test_bad_name_is_asked_again_without_advancing(
    update, context, replies, monkeypatch
) -> None:
    _bridge(monkeypatch, status={"signed": False})

    await nda.open_signing(update, context)
    await _press(update, context, "begin")
    await nda.handle_message(update, context, "Иван")

    assert context.user_data[nda.STAGE_KEY] == nda.STAGE_NAME
    assert "фамилия" in replies[-1].lower()


@pytest.mark.anyio
async def test_bad_contact_is_asked_again(update, context, replies, monkeypatch) -> None:
    _bridge(monkeypatch, status={"signed": False})

    await nda.open_signing(update, context)
    await _press(update, context, "begin")
    await nda.handle_message(update, context, "Иванов Иван Иванович")
    await nda.handle_message(update, context, "потом скажу")

    assert context.user_data[nda.STAGE_KEY] == nda.STAGE_CONTACT


@pytest.mark.anyio
async def test_reading_the_text_records_its_checksum(
    update, context, replies, monkeypatch
) -> None:
    """Подпись должна относиться к той редакции, которую человек прочитал."""
    calls = _bridge(monkeypatch, status={"signed": False})

    await nda.open_signing(update, context)
    await _press(update, context, "text")
    assert context.user_data[nda.HASH_KEY] == "abc"

    await _press(update, context, "begin")
    await nda.handle_message(update, context, "Иванов Иван Иванович")
    await nda.handle_message(update, context, "ivan@example.ru")
    await nda.handle_message(update, context, "от себя")
    await _press(update, context, "confirm")

    assert calls["sign"]["document_hash"] == "abc"


@pytest.mark.anyio
async def test_cancel_leaves_no_state_and_reassures(update, context, replies, monkeypatch) -> None:
    """Отказ не должен читаться как отказ в помощи."""
    _bridge(monkeypatch, status={"signed": False})

    await nda.open_signing(update, context)
    await _press(update, context, "begin")
    await _press(update, context, "cancel")

    assert nda.STAGE_KEY not in context.user_data
    assert "без него" in replies[-1]


@pytest.mark.anyio
async def test_failed_signing_does_not_leave_the_client_guessing(
    update, context, replies, monkeypatch
) -> None:
    _bridge(monkeypatch, status={"signed": False}, sign_result=None)

    await nda.open_signing(update, context)
    await _press(update, context, "begin")
    await nda.handle_message(update, context, "Иванов Иван Иванович")
    await nda.handle_message(update, context, "ivan@example.ru")
    await nda.handle_message(update, context, "от себя")
    await _press(update, context, "confirm")

    assert "не удалось" in replies[-1].lower()
    # Документы всё равно примем — отказ подписания не должен блокировать дело.
    assert "без соглашения" in replies[-1]


@pytest.mark.anyio
async def test_messages_outside_the_flow_are_not_intercepted(update, replies) -> None:
    context = SimpleNamespace(user_data={})
    assert await nda.handle_message(update, context, "просто сообщение") is False
