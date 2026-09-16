"""Аудит 16.09 после переноса лидов в ядро: business-чат и операторские кнопки.

Кейс Виктории: «Андрей, добрый день. Это Фролова Виктория, компания …» с
телефоном в подписи стал тёплым лидом с handoff и уведомлением «новый лид»
(10:42), а операторская кнопка «Личное обращение» четыре раза подряд падала
с Business_peer_invalid и заводила лид заново (13:20).
"""
from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace

import pytest
from telegram.error import BadRequest

import bot as bot_module
import config as config_module
import core_api_bridge as bridge_module
import database_reporting
from database import Database
from handlers import business


@pytest.fixture
def test_db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(db_path)
    yield db
    if os.path.exists(db_path):
        os.unlink(db_path)


VIKTORIA_TEXT = (
    "Андрей, добрый день.\n\n"
    'Это Фролова Виктория, компания "Совет". Хотела бы обсудить сотрудничество.\n'
    "Мой телефон +7 967 551 04 48"
)


def _business_update(text: str, *, user_id: int = 8858959680, chat_id: int = 8858959680):
    return SimpleNamespace(
        business_message=SimpleNamespace(
            text=text,
            contact=None,
            from_user=SimpleNamespace(id=user_id, username="viktoria", first_name="Виктория", last_name=None),
            business_connection_id="bc-1",
            chat=SimpleNamespace(id=chat_id),
        ),
        edited_business_message=None,
        message=None,
        update_id=1001,
    )


# --- детекторы -------------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        (VIKTORIA_TEXT, True),
        ("Добрый день, Андрей! Это Виктория", True),
        ("Здравствуйте, Андрей Николаевич, вопрос по договору", True),
        ("Мне сказал Андрей, что вы делаете проверку договоров", False),
        ("Добрый день! Нужна консультация по договору аренды", False),
        ("Андреевка — это наш посёлок, нужна помощь", False),
        ("/start", False),
        ("", False),
    ],
)
def test_personal_address_to_owner_detector(text, expected):
    assert business._looks_like_personal_address_to_owner(text) is expected


def test_bare_phone_message_detector():
    assert business._looks_like_bare_phone_message("мой номер +7 999 123-45-67")
    assert business._looks_like_bare_phone_message("+79991234567, перезвоните пожалуйста")
    assert not business._looks_like_bare_phone_message(VIKTORIA_TEXT)


# --- личное обращение к владельцу: без лида, без ответа, чат → personal -----

@pytest.mark.asyncio
async def test_personal_message_to_owner_is_not_a_lead(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict] = []
    modes: list[tuple[int, str]] = []
    events: list[str] = []

    monkeypatch.setattr(business, "_is_business_processing_allowed", lambda message: True)
    monkeypatch.setattr(business.database.db, "create_or_update_user", lambda **kwargs: 252)
    monkeypatch.setattr(business.database.db, "get_chat_mode", lambda chat_id: "bot")
    monkeypatch.setattr(business.database.db, "set_chat_mode", lambda chat_id, mode: modes.append((chat_id, mode)))
    monkeypatch.setattr(business.database.db, "track_event", lambda user_id, event_type, payload=None, lead_id=None: events.append(event_type))

    def _fail(*args, **kwargs):
        raise AssertionError("личное обращение не должно заводить лид")

    monkeypatch.setattr(business.database.db, "create_new_lead", _fail)
    monkeypatch.setattr(business.database.db, "create_or_update_lead", _fail)
    monkeypatch.setattr(business, "_send_business_handoff_and_notify", _fail)

    async def _fake_send_message(**kwargs):
        sent.append(kwargs)

    context = SimpleNamespace(bot=SimpleNamespace(send_message=_fake_send_message), user_data={})
    await business.handle_business_message(_business_update(VIKTORIA_TEXT), context)

    assert sent == []
    assert modes == [(8858959680, "personal")]
    assert events == ["personal_message_detected"]


# --- телефон в свободном тексте не равен «перезвоните» ----------------------

@pytest.mark.asyncio
async def test_phone_inside_free_text_does_not_trigger_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Описание задачи с реквизитами: телефон есть, просьбы перезвонить нет."""
    text = (
        "Добрый день! Нужна проверка договора поставки с ООО «Ромашка», "
        "их контакт для связи +7 999 123-45-67, договор пришлю файлом."
    )
    handoffs: list[str] = []

    monkeypatch.setattr(business, "_is_business_processing_allowed", lambda message: True)
    monkeypatch.setattr(business.database.db, "create_or_update_user", lambda **kwargs: 300)
    monkeypatch.setattr(business.database.db, "get_chat_mode", lambda chat_id: "bot")
    monkeypatch.setattr(business, "_should_force_business_welcome", lambda *a, **k: False)
    monkeypatch.setattr(business.database.db, "get_lead_by_user_id", lambda user_id: None)
    monkeypatch.setattr(business.database.db, "get_user_funnel_state", lambda user_id: {"conversation_stage": "discover"})

    def _fail_lead(*args, **kwargs):
        raise AssertionError("телефон внутри описания не должен заводить лид с handoff")

    monkeypatch.setattr(business.database.db, "create_new_lead", _fail_lead)

    async def _fail_handoff(**kwargs):
        handoffs.append("called")

    monkeypatch.setattr(business, "_send_business_handoff_and_notify", _fail_handoff)
    monkeypatch.setattr(business.ai_brain.ai_brain, "check_handoff_trigger", lambda text: False)
    monkeypatch.setattr(business.funnel, "should_fast_track_handoff", lambda text, lead: False)

    # Дальше по коду — обычная обработка (AI-ответ); её отрезаем, чтобы тест
    # проверял только, что ветка «телефон = handoff» не сработала.
    class _Stop(Exception):
        pass

    monkeypatch.setattr(business.database.db, "add_message", lambda *a, **k: (_ for _ in ()).throw(_Stop()))

    async def _fake_send_message(**kwargs):
        return None

    context = SimpleNamespace(bot=SimpleNamespace(send_message=_fake_send_message), user_data={})
    try:
        await business.handle_business_message(_business_update(text, user_id=300, chat_id=300), context)
    except _Stop:
        pass

    assert handoffs == []


@pytest.mark.asyncio
async def test_bare_phone_message_still_captured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Прислали по сути один номер — это и есть просьба связаться."""
    captured: list[dict] = []
    handoffs: list[str] = []

    monkeypatch.setattr(business, "_is_business_processing_allowed", lambda message: True)
    monkeypatch.setattr(business.database.db, "create_or_update_user", lambda **kwargs: 301)
    monkeypatch.setattr(business.database.db, "get_chat_mode", lambda chat_id: "bot")
    monkeypatch.setattr(business, "_should_force_business_welcome", lambda *a, **k: False)
    monkeypatch.setattr(business.database.db, "get_lead_by_user_id", lambda user_id: None)
    monkeypatch.setattr(business.database.db, "get_user_funnel_state", lambda user_id: {"conversation_stage": "discover"})
    monkeypatch.setattr(business.database.db, "create_new_lead", lambda user_id, payload: captured.append(payload) or 55)
    monkeypatch.setattr(business.database.db, "update_lead_last_message_time", lambda user_id: None)

    async def _fake_handoff(**kwargs):
        handoffs.append(kwargs["source"])
        return 55

    monkeypatch.setattr(business, "_send_business_handoff_and_notify", _fake_handoff)

    async def _fake_send_message(**kwargs):
        return None

    context = SimpleNamespace(bot=SimpleNamespace(send_message=_fake_send_message), user_data={})
    await business.handle_business_message(_business_update("мой номер +7 999 123-45-67", user_id=301, chat_id=301), context)

    assert captured and captured[0]["phone"] == "+79991234567"
    assert handoffs == ["business_phone_capture:consultation"]


# --- операторская кнопка: Business_peer_invalid не роняет обработчик --------

@pytest.mark.asyncio
async def test_operator_personal_handoff_survives_business_peer_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    modes: list[tuple[int, str]] = []
    monkeypatch.setattr(business.database.db, "create_or_update_user", lambda **kwargs: 252)
    monkeypatch.setattr(business.database.db, "set_chat_mode", lambda chat_id, mode: modes.append((chat_id, mode)))
    monkeypatch.setattr(business.database.db, "track_event", lambda *a, **k: None)

    async def _peer_invalid(**kwargs):
        raise BadRequest("Business_peer_invalid")

    context = SimpleNamespace(bot=SimpleNamespace(send_message=_peer_invalid), user_data={})
    message = SimpleNamespace(chat=SimpleNamespace(id=8858959680, username=None, first_name="Виктория", last_name=None), business_connection_id="bc-old")
    operator = SimpleNamespace(id=321681061, full_name="Andrew Popov", first_name="Andrew")

    lead_id = await business.handle_business_operator_handoff(
        context=context, message=message, operator_user=operator, trigger="callback:menu_personal_request", mode="personal_request"
    )

    assert lead_id is None
    assert modes == [(8858959680, "personal")]  # режим переключён, несмотря на несостоявшееся подтверждение клиенту


@pytest.mark.asyncio
async def test_operator_callback_is_answered_even_if_handoff_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    answers: list[dict] = []

    monkeypatch.setattr(bot_module, "_is_trusted_business_operator_callback", lambda query: True)

    async def _boom(**kwargs):
        raise RuntimeError("core-api down")

    monkeypatch.setattr(bot_module, "handle_business_operator_handoff", _boom)

    async def _fake_answer(query, **kwargs):
        answers.append(kwargs)

    monkeypatch.setattr(bot_module.utils, "safe_answer_callback", _fake_answer)

    query = SimpleNamespace(data="menu_personal_request", message=SimpleNamespace(chat=SimpleNamespace(id=1)), from_user=SimpleNamespace(id=321681061))
    update = SimpleNamespace(callback_query=query, update_id=5)
    handled = await bot_module._try_handle_business_operator_callback(update, SimpleNamespace(user_data={}))

    assert handled is True
    assert len(answers) == 1 and answers[0]["show_alert"] is True and "core-api down" in answers[0]["text"]


# --- таймаут реплики помощника -------------------------------------------

def test_assistant_turn_uses_dedicated_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge_module.config, "CORE_API_ASSISTANT_TURN_TIMEOUT_SECONDS", 50.0)
    bridge = bridge_module.CoreApiBridge()
    bridge.enabled = True
    bridge.timeout = 5.0
    seen = {}

    def _fake_post(path, payload, idempotency_key, *, timeout=None):
        seen["timeout"] = timeout
        return {"ok": True, "reply": "…"}

    monkeypatch.setattr(bridge, "_post", _fake_post)
    bridge.assistant_turn("intake-1", history=[], base_questions=[], area_label="иное", asked_count=0)
    assert seen["timeout"] == 50.0


def test_assistant_turn_timeout_default_covers_core_llm_budget():
    assert config_module.get_config().CORE_API_ASSISTANT_TURN_TIMEOUT_SECONDS >= 45.0


# --- /stats: лиды из ядра ---------------------------------------------------

def test_statistics_count_leads_from_core(test_db):
    rows = [
        {"temperature": "hot", "lead_magnet_type": "consultation"},
        {"temperature": "warm", "lead_magnet_type": "demo"},
        {"temperature": "warm", "lead_magnet_type": None},
    ]
    stats = database_reporting.get_statistics(test_db.get_connection, days=30, leads_provider=lambda: rows)
    assert stats["total_leads"] == 3
    assert stats["hot_leads"] == 1 and stats["warm_leads"] == 2 and stats["cold_leads"] == 0
    assert stats["consultations"] == 1 and stats["demos"] == 1 and stats["checklists"] == 0


def test_statistics_fall_back_to_local_when_core_fails(test_db):
    def _boom():
        raise RuntimeError("core-api unreachable")

    stats = database_reporting.get_statistics(test_db.get_connection, days=30, leads_provider=_boom)
    assert stats["total_leads"] == 0  # локальная таблица пуста, но статистика не упала
