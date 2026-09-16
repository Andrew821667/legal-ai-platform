"""
Тесты для database.py - проверка работы с базой данных
"""
import pytest
import tempfile
import os
import time
import json
from database import Database
from tests.fake_core import install as install_fake_core


@pytest.fixture
def test_db():
    """Создание временной тестовой базы данных"""
    # Создаем временный файл для БД
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Инициализируем БД
    db = Database(db_path)

    yield db

    # Удаляем временный файл после теста
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_database_initialization(test_db):
    """Проверка что БД инициализируется корректно"""
    conn = test_db.get_connection()
    cursor = conn.cursor()

    # Проверяем что все таблицы созданы
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    assert 'users' in tables, "Таблица users не создана"
    assert 'conversations' in tables, "Таблица conversations не создана"
    assert 'leads' in tables, "Таблица leads не создана"
    assert 'admin_notifications' in tables, "Таблица admin_notifications не создана"
    assert 'chat_states' in tables, "Таблица chat_states не создана"
    assert 'business_connection_states' in tables, "Таблица business_connection_states не создана"

    conn.close()


def test_create_user(test_db):
    """Проверка создания пользователя"""
    user_id = test_db.create_or_update_user(
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        last_name="User"
    )

    assert user_id > 0, "Пользователь не создан"

    # Проверяем что пользователь сохранен
    user = test_db.get_user_by_telegram_id(123456789)
    assert user is not None, "Пользователь не найден"
    assert user['username'] == "testuser"
    assert user['first_name'] == "Test"


def test_add_message(test_db):
    """Проверка добавления сообщения"""
    # Создаем пользователя
    user_id = test_db.create_or_update_user(
        telegram_id=123456789,
        username="testuser",
        first_name="Test"
    )

    # Добавляем сообщение
    test_db.add_message(user_id, 'user', 'Test message')

    # Проверяем что сообщение сохранено
    history = test_db.get_conversation_history(user_id)
    assert len(history) == 1, "Сообщение не сохранено"
    assert history[0]['message'] == 'Test message'
    assert history[0]['role'] == 'user'


def test_cleanup_conversations_by_retention(test_db):
    user_id = test_db.create_or_update_user(
        telegram_id=987654321,
        username="retention_user",
        first_name="Retention",
    )
    test_db.add_message(user_id, 'user', 'Old message')
    test_db.add_message(user_id, 'assistant', 'Fresh message')

    conn = test_db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE conversations
        SET timestamp = datetime('now', '-120 days')
        WHERE user_id = ? AND role = 'user'
        """,
        (user_id,),
    )
    conn.commit()
    conn.close()

    deleted = test_db.cleanup_conversations_by_retention(90)
    history = test_db.get_conversation_history(user_id, limit=10)

    assert deleted == 1
    assert len(history) == 1
    assert history[0]["message"] == "Fresh message"


def test_create_lead(test_db, monkeypatch):
    """Лид пишется в ядро и читается оттуда же; номер выдаёт ядро."""
    core = install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(telegram_id=123456789, username="testuser", first_name="Test")

    lead_id = test_db.create_or_update_lead(user_id, {"name": "Test Lead", "email": "test@example.com", "temperature": "hot"})

    assert lead_id > 0
    assert core.leads[0]["telegram_user_id"] == 123456789
    lead = test_db.get_lead_by_user_id(user_id)
    assert lead is not None
    assert lead["id"] == lead_id
    assert lead["user_id"] == user_id
    assert lead["core_lead_id"] == core.leads[0]["id"]
    assert lead["name"] == "Test Lead"
    assert lead["email"] == "test@example.com"
    assert lead["temperature"] == "hot"
    # В SQLite ни одной строки лида не появилось.
    conn = test_db.get_connection()
    assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0
    conn.close()


def test_pending_leads_are_read_from_core_working_queue(test_db, monkeypatch):
    """Очередь уведомлений — в ядре: бот берёт готовые лиды оттуда с номером и UUID."""
    from datetime import datetime, timedelta, timezone

    core = install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(telegram_id=321001, username="pending", first_name="Pending")
    lead_id = test_db.create_or_update_lead(
        user_id, {"name": "Pending Lead", "temperature": "warm", "pain_point": "Нужна автоматизация"}
    )
    test_db.update_lead_last_message_time(user_id)
    assert core.leads[0]["last_message_at"] is not None
    core.leads[0]["last_message_at"] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    rows = test_db.get_leads_ready_for_notification(idle_minutes=1)

    assert len(rows) == 1
    assert rows[0]["id"] == lead_id
    assert rows[0]["user_id"] == user_id
    assert rows[0]["core_lead_id"] == core.leads[0]["id"]
    assert rows[0]["name"] == "Pending Lead"

    test_db.mark_lead_notification_sent(lead_id)
    assert core.notified == [core.leads[0]["id"]]
    assert test_db.get_leads_ready_for_notification(idle_minutes=1) == []


def test_pending_lead_delivery_waits_when_core_queue_is_unavailable(test_db, monkeypatch):
    core = install_fake_core(monkeypatch, test_db)
    core.down = True

    assert test_db.get_leads_ready_for_notification(idle_minutes=1) == []


def test_get_statistics(test_db):
    """Проверка получения статистики"""
    # Создаем тестовые данные
    user_id = test_db.create_or_update_user(
        telegram_id=123456789,
        username="testuser",
        first_name="Test"
    )
    test_db.add_message(user_id, 'user', 'Test message')

    # Получаем статистику
    stats = test_db.get_statistics()

    assert stats is not None, "Статистика не получена"
    assert stats['total_users'] >= 1, "Количество пользователей некорректно"
    assert stats['total_messages'] >= 1, "Количество сообщений некорректно"


def test_get_recent_users_with_offset_and_count(test_db):
    test_db.create_or_update_user(telegram_id=810001, username="u1", first_name="U1")
    test_db.create_or_update_user(telegram_id=810002, username="u2", first_name="U2")
    test_db.create_or_update_user(telegram_id=810003, username="u3", first_name="U3")

    first_page = test_db.get_recent_users(limit=2, offset=0)
    second_page = test_db.get_recent_users(limit=2, offset=2)

    assert test_db.count_users() == 3
    assert len(first_page) == 2
    assert len(second_page) == 1
    assert first_page[0]["telegram_id"] == 810003
    assert second_page[0]["telegram_id"] == 810001


def test_user_offer_profile_and_consent_filters(test_db):
    user_id = test_db.create_or_update_user(telegram_id=820001, username="offer", first_name="Offer")
    revoked_id = test_db.create_or_update_user(telegram_id=820002, username="revoked", first_name="Revoked")

    test_db.set_user_offer_profile(user_id, "business")
    assert test_db.get_user_offer_profile(user_id) == "business"

    test_db.grant_user_consent(user_id)
    test_db.grant_user_consent(revoked_id)
    summary = test_db.revoke_user_consent_and_delete_data(revoked_id)

    without_consent = test_db.get_users_without_consent(limit=10)
    revoked_users = test_db.get_users_with_revoked_consent(limit=10)

    assert summary["users_updated"] == 1
    assert all(row["telegram_id"] != 820001 for row in without_consent)
    assert any(row["telegram_id"] == 820002 for row in revoked_users)


def test_chat_and_business_connection_state_roundtrip(test_db):
    chat_id = 930001
    connection_id = "bc-test-1"

    assert test_db.is_chat_enabled(chat_id) is True
    assert test_db.get_chat_mode(chat_id) == "bot"

    test_db.set_chat_enabled(chat_id, False)
    assert test_db.is_chat_enabled(chat_id) is False
    assert chat_id in test_db.get_disabled_chats()

    test_db.set_chat_mode(chat_id, "personal")
    assert test_db.get_chat_mode(chat_id) == "personal"

    assert test_db.is_business_connection_enabled(connection_id) is True
    test_db.set_business_connection_state(connection_id, user_chat_id=chat_id, is_enabled=False)
    assert test_db.is_business_connection_enabled(connection_id) is False


def test_security_message_events_count_and_prune(test_db):
    now = int(time.time())
    user_id = 555123

    test_db.record_security_message_event(user_id, now - 70)
    test_db.record_security_message_event(user_id, now - 20)
    test_db.record_security_message_event(user_id, now - 5)

    assert test_db.count_security_message_events_since(user_id, now - 60) == 2
    assert test_db.count_security_message_events_since(user_id, now - 3600) == 3

    deleted = test_db.prune_security_message_events(now - 30, telegram_user_id=user_id)
    assert deleted == 1
    assert test_db.count_security_message_events_since(user_id, now - 3600) == 2


def test_security_token_usage_daily_aggregates(test_db):
    user_id = 555124
    day_key = "2026-03-06"
    prev_day = "2026-03-05"

    test_db.add_security_tokens_used(user_id, day_key, 1000)
    test_db.add_security_tokens_used(user_id, day_key, 250)
    test_db.add_security_tokens_used(user_id, prev_day, 700)

    assert test_db.get_security_user_tokens(user_id, day_key) == 1250
    assert test_db.get_security_user_tokens_since(user_id, prev_day) == 1950
    assert test_db.get_security_total_tokens(day_key) == 1250


def test_security_blacklist_crud(test_db):
    telegram_user_id = 991001

    assert test_db.count_security_blacklist() == 0

    test_db.add_security_blacklist(telegram_user_id, "spam")
    entry = test_db.get_security_blacklist_entry(telegram_user_id)
    assert entry is not None
    assert entry["telegram_user_id"] == telegram_user_id
    assert entry["reason"] == "spam"
    assert test_db.count_security_blacklist() == 1

    test_db.add_security_blacklist(telegram_user_id, "updated")
    updated_entry = test_db.get_security_blacklist_entry(telegram_user_id)
    assert updated_entry is not None
    assert updated_entry["reason"] == "updated"

    listed = test_db.list_security_blacklist(limit=10)
    assert listed[0]["telegram_user_id"] == telegram_user_id

    removed = test_db.remove_security_blacklist(telegram_user_id)
    assert removed == 1
    assert test_db.get_security_blacklist_entry(telegram_user_id) is None
    assert test_db.count_security_blacklist() == 0


def test_security_cooldown_suspicious_and_reset(test_db):
    telegram_user_id = 991002
    now = time.time()
    day_key = "2026-03-06"

    test_db.set_security_cooldown(telegram_user_id, now)
    cooldown_ts = test_db.get_security_cooldown(telegram_user_id)
    assert cooldown_ts is not None
    assert abs(cooldown_ts - now) < 1.0

    assert test_db.increment_security_suspicious(telegram_user_id) == 1
    assert test_db.increment_security_suspicious(telegram_user_id) == 2
    assert test_db.count_security_suspicious_users() == 1

    test_db.record_security_message_event(telegram_user_id, int(now))
    test_db.add_security_tokens_used(telegram_user_id, day_key, 123)
    test_db.add_security_blacklist(telegram_user_id, "test")

    test_db.reset_security_counters(clear_blacklist=False)
    assert test_db.count_security_message_events_since(telegram_user_id, 0) == 0
    assert test_db.get_security_user_tokens(telegram_user_id, day_key) == 0
    assert test_db.get_security_cooldown(telegram_user_id) is None
    assert test_db.count_security_suspicious_users() == 0
    assert test_db.count_security_blacklist() == 1

    test_db.reset_security_counters(clear_blacklist=True)
    assert test_db.count_security_blacklist() == 0


def test_security_action_events_incidents_and_quarantine(test_db):
    telegram_user_id = 991003
    now = int(time.time())

    test_db.record_security_action_event(telegram_user_id, "callback:any", now - 2)
    test_db.record_security_action_event(telegram_user_id, "callback:any", now - 1)
    test_db.record_security_action_event(telegram_user_id, "non_text:document", now - 1)

    assert test_db.count_security_action_events_since(telegram_user_id, "callback:any", now - 10) == 2
    assert test_db.count_security_action_events_since(telegram_user_id, "non_text:document", now - 10) == 1

    incident_id = test_db.record_security_incident(
        telegram_user_id=telegram_user_id,
        chat_id=telegram_user_id,
        update_id=123,
        update_type="callback_query",
        action="blocked_soft",
        reason_code="callback_rate_limited",
        severity="warning",
        payload={"callback_count": 12},
        ts_epoch=now,
    )
    assert incident_id > 0

    incidents = test_db.list_security_incidents(limit=5, telegram_user_id=telegram_user_id)
    assert incidents
    assert incidents[0]["reason_code"] == "callback_rate_limited"
    assert incidents[0]["action"] == "blocked_soft"

    test_db.upsert_security_quarantine(
        telegram_user_id,
        status="active",
        reason_code="from_user_is_bot",
        strikes=3,
        quarantined_until_epoch=now + 3600,
    )
    entry = test_db.get_security_quarantine_entry(telegram_user_id)
    assert entry is not None
    assert entry["status"] == "active"
    assert entry["reason_code"] == "from_user_is_bot"
    assert test_db.count_security_quarantine() == 1

    removed = test_db.clear_security_quarantine(telegram_user_id)
    assert removed == 1
    assert test_db.get_security_quarantine_entry(telegram_user_id) is None


def test_consent_flow_and_data_export(test_db, monkeypatch):
    """Проверка цикла согласия/экспорта/отзыва согласия."""
    install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(
        telegram_id=777000111,
        username="consent_user",
        first_name="Consent",
        last_name="Tester",
    )
    test_db.create_or_update_lead(
        user_id,
        {
            "name": "Consent Tester",
            "email": "consent@example.com",
            "phone": "+79001234567",
            "company": "Legal AI",
        },
    )
    test_db.add_message(user_id, "user", "test message")

    state_before = test_db.get_user_consent_state(user_id)
    assert not bool(state_before["consent_given"])
    assert not bool(state_before["transborder_consent"])

    test_db.grant_user_consent(user_id)
    test_db.set_user_transborder_consent(user_id, True)

    payload = test_db.export_user_data(user_id)
    assert payload["user"]["telegram_id"] == 777000111
    assert payload["lead"]["email"] == "consent@example.com"
    assert payload["consent"]["consent_given"] is True
    assert payload["consent"]["transborder_consent"] is True

    # Локальный запас на случай недоступности ядра: согласия и переписка.
    # Сам лид обезличивает ядро (gdpr-clear) — это его данные.
    cleanup = test_db.revoke_user_consent_and_delete_data(user_id)
    assert cleanup["users_updated"] == 1
    assert cleanup["messages_deleted"] >= 1
    assert cleanup["leads_anonymized"] == 0


def test_get_successful_conversations_returns_grouped_messages(test_db, monkeypatch):
    """RAG-выборка: лиды из ядра, переписка из SQLite, ничего не теряется."""
    install_fake_core(monkeypatch, test_db)
    first_user_id = test_db.create_or_update_user(telegram_id=10001, username="rag_user_1", first_name="Rag")
    second_user_id = test_db.create_or_update_user(telegram_id=10002, username="rag_user_2", first_name="RagTwo")
    cold_user_id = test_db.create_or_update_user(telegram_id=10009, username="rag_cold", first_name="Cold")

    test_db.create_or_update_lead(
        first_user_id,
        {"name": "Rag User 1", "temperature": "warm", "service_category": "contracts", "pain_point": "Долго согласуем договоры"},
    )
    test_db.create_or_update_lead(
        second_user_id,
        {"name": "Rag User 2", "temperature": "hot", "service_category": "claims", "pain_point": "Большой поток претензий"},
    )
    test_db.create_or_update_lead(cold_user_id, {"name": "Cold", "temperature": "cold", "pain_point": "Просто смотрю"})

    test_db.add_message(first_user_id, "user", "Первое сообщение")
    test_db.add_message(first_user_id, "assistant", "Ответ ассистента")
    test_db.add_message(second_user_id, "user", "Второе сообщение")

    result = test_db.get_successful_conversations(limit=10)

    assert len(result) == 2
    by_user = {item["user_id"]: item for item in result}
    assert [msg["message"] for msg in by_user[first_user_id]["messages"]] == ["Первое сообщение", "Ответ ассистента"]
    assert [msg["message"] for msg in by_user[second_user_id]["messages"]] == ["Второе сообщение"]


def test_get_all_leads_supports_offset_pagination(test_db, monkeypatch):
    install_fake_core(monkeypatch, test_db)
    user_a = test_db.create_or_update_user(telegram_id=12001, username="l_a", first_name="A")
    user_b = test_db.create_or_update_user(telegram_id=12002, username="l_b", first_name="B")
    user_c = test_db.create_or_update_user(telegram_id=12003, username="l_c", first_name="C")

    lead_a = test_db.create_or_update_lead(user_a, {"name": "Lead A", "temperature": "cold"})
    lead_b = test_db.create_or_update_lead(user_b, {"name": "Lead B", "temperature": "warm"})
    lead_c = test_db.create_or_update_lead(user_c, {"name": "Lead C", "temperature": "hot"})

    page1 = test_db.get_all_leads(limit=2, offset=0)
    page2 = test_db.get_all_leads(limit=2, offset=2)

    assert [item["id"] for item in page1] == [lead_c, lead_b]
    assert [item["id"] for item in page2] == [lead_a]


def test_get_successful_conversations_supports_offset(test_db, monkeypatch):
    install_fake_core(monkeypatch, test_db)
    user_a = test_db.create_or_update_user(telegram_id=13001, username="rag_a", first_name="RagA")
    user_b = test_db.create_or_update_user(telegram_id=13002, username="rag_b", first_name="RagB")
    user_c = test_db.create_or_update_user(telegram_id=13003, username="rag_c", first_name="RagC")

    test_db.create_or_update_lead(
        user_a,
        {"name": "Rag A", "temperature": "warm", "service_category": "contracts", "pain_point": "pain A"},
    )
    test_db.create_or_update_lead(
        user_b,
        {"name": "Rag B", "temperature": "warm", "service_category": "contracts", "pain_point": "pain B"},
    )
    test_db.create_or_update_lead(
        user_c,
        {"name": "Rag C", "temperature": "hot", "service_category": "contracts", "pain_point": "pain C"},
    )

    page1 = test_db.get_successful_conversations(limit=2, offset=0)
    page2 = test_db.get_successful_conversations(limit=2, offset=2)

    assert len(page1) == 2
    assert len(page2) == 1


def test_lead_number_and_core_id_come_from_core(test_db, monkeypatch):
    """Связь номер ↔ UUID хранит ядро; set_core_lead_id оставлен пустым для совместимости."""
    core = install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(telegram_id=10003, username="core_sync_user", first_name="Core")
    lead_id = test_db.create_or_update_lead(user_id, {"name": "Core Sync", "temperature": "warm"})

    test_db.set_core_lead_id(lead_id, "11111111-1111-1111-1111-111111111111")

    lead = test_db.get_lead_by_id(lead_id)
    assert lead["core_lead_id"] == core.leads[0]["id"]
    assert lead["id"] == lead_id == core.leads[0]["legacy_lead_id"]


def test_core_only_lead_does_not_break_local_analytics(test_db, monkeypatch):
    """Core lead numbers must not be treated as SQLite foreign keys."""
    install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(
        telegram_id=10008,
        username="analytics_core_lead",
        first_name="Analytics",
    )
    lead_id = test_db.create_new_lead(user_id, {"name": "Core-only lead"})

    event_id = test_db.track_event(
        user_id,
        "legal_help_submitted",
        payload={"core_confirmed": True},
        lead_id=lead_id,
    )

    conn = test_db.get_connection()
    row = conn.execute(
        "SELECT lead_id, event_type FROM analytics_events WHERE id = ?",
        (event_id,),
    ).fetchone()
    conn.close()

    assert event_id > 0
    assert row["event_type"] == "legal_help_submitted"
    assert row["lead_id"] is None


def test_core_only_lead_skips_legacy_notification_journal(test_db, monkeypatch):
    install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(
        telegram_id=10009,
        username="notification_core_lead",
        first_name="Notification",
    )
    lead_id = test_db.create_new_lead(user_id, {"name": "Core-only lead"})

    notification_id = test_db.create_notification(lead_id, "new_lead", "sent")

    conn = test_db.get_connection()
    count = conn.execute("SELECT COUNT(*) FROM admin_notifications").fetchone()[0]
    conn.close()

    assert notification_id == 0
    assert count == 0


def test_local_analytics_failure_does_not_break_client_flow(test_db):
    event_id = test_db.track_event(
        999999,
        "client_message",
        payload={"source": "telegram"},
    )

    assert event_id == 0


def test_reset_user_to_new_state_keeps_profile_and_clears_data(test_db, monkeypatch):
    """Локальный сброс: переписка, события, согласия. Лиды сбрасывает ядро (reset-new)."""
    install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(
        telegram_id=10005,
        username="reset_user",
        first_name="Reset",
        last_name="Candidate",
    )
    test_db.grant_user_consent(user_id)
    test_db.set_user_transborder_consent(user_id, True)
    test_db.add_message(user_id, "user", "старое сообщение")
    test_db.track_event(user_id, "stage_changed", payload={"from": "discover", "to": "diagnose"})

    result = test_db.reset_user_to_new_state(user_id)
    assert result["users_reset"] == 1
    assert result["leads_deleted"] == 0
    assert result["messages_deleted"] >= 1
    assert result["events_deleted"] >= 1

    user = test_db.get_user_by_id(user_id)
    assert user is not None
    assert bool(user["consent_given"]) is False
    assert bool(user["transborder_consent"]) is False
    assert user["conversation_stage"] == "discover"
    assert test_db.get_conversation_history(user_id) == []


def test_delete_user_completely_removes_profile_and_related_data(test_db, monkeypatch):
    install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(
        telegram_id=10006,
        username="delete_user",
        first_name="Delete",
        last_name="Candidate",
    )
    test_db.add_message(user_id, "user", "какой-то диалог")
    test_db.track_event(user_id, "cta_clicked", payload={"variant": "a"})

    result = test_db.delete_user_completely(user_id)
    assert result["users_deleted"] == 1
    assert result["leads_deleted"] == 0
    assert result["messages_deleted"] >= 1
    assert result["events_deleted"] >= 1

    assert test_db.get_user_by_id(user_id) is None
    assert test_db.get_user_by_telegram_id(10006) is None


def test_create_or_update_lead_writes_to_core_only(test_db, monkeypatch):
    """Обновление идёт в последний лид аккаунта; новый лид — только явно."""
    core = install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(telegram_id=10004, username="bridge_user", first_name="Bridge")

    lead_id = test_db.create_or_update_lead(
        user_id, {"name": "Bridge Lead", "temperature": "warm", "pain_point": "Нужен sync в core-api"}
    )
    same_id = test_db.create_or_update_lead(user_id, {"email": "bridge@example.com", "lead_temperature": "hot"})
    assert same_id == lead_id
    assert len(core.leads) == 1
    assert core.leads[0]["email"] == "bridge@example.com"
    assert core.leads[0]["temperature"] == "hot"
    assert core.leads[0]["pain_point"] == "Нужен sync в core-api"

    new_id = test_db.create_new_lead(user_id, {"name": "Второе обращение"})
    assert new_id != lead_id
    assert len(core.leads) == 2
    assert test_db.get_lead_by_user_id(user_id)["id"] == new_id


def test_create_or_update_user_syncs_to_core_bridge(test_db, monkeypatch):
    captured = {}

    class StubBridge:
        enabled = True

        @staticmethod
        def sync_user(user):
            captured["telegram_id"] = user["telegram_id"]
            captured["username"] = user["username"]
            captured["consent_given"] = bool(user["consent_given"])
            return "user-core-id"

    import core_api_bridge

    monkeypatch.setattr(core_api_bridge, "core_api_bridge", StubBridge())

    user_id = test_db.create_or_update_user(
        telegram_id=10005,
        username="bridge_user_sync",
        first_name="User",
    )
    test_db.grant_user_consent(user_id)

    assert captured["telegram_id"] == 10005
    assert captured["username"] == "bridge_user_sync"
    assert captured["consent_given"] is True


def test_get_user_by_telegram_id_prefers_core_snapshot(test_db, monkeypatch):
    user_id = test_db.create_or_update_user(
        telegram_id=10006,
        username="local_user",
        first_name="Local",
        last_name="User",
    )
    assert user_id > 0

    monkeypatch.setattr(
        test_db,
        "_core_get_json",
        lambda path, params=None: [
            {
                "telegram_id": 10006,
                "username": "core_user",
                "first_name": "Core",
                "last_name": "User",
                "consent_given": True,
                "consent_revoked": False,
                "transborder_consent": True,
                "marketing_consent": False,
                "cta_shown": True,
            }
        ]
        if path == "/api/v1/users" and params and params.get("telegram_id") == 10006
        else None,
    )

    user = test_db.get_user_by_telegram_id(10006)

    assert user is not None
    assert user["username"] == "core_user"
    assert user["first_name"] == "Core"
    assert bool(user["consent_given"]) is True
    assert bool(user["transborder_consent"]) is True


def test_lead_reads_are_cached_briefly_and_refreshed_after_write(test_db, monkeypatch):
    core = install_fake_core(monkeypatch, test_db)
    user_id = test_db.create_or_update_user(telegram_id=10007, username="lead_local", first_name="Lead")
    test_db.create_or_update_lead(user_id, {"name": "Local Lead", "company": "Local Co", "temperature": "cold"})

    first = test_db.get_lead_by_user_id(user_id)
    reads_before = len([call for call in core.calls if call[0] == "GET"])
    second = test_db.get_lead_by_user_id(user_id)
    reads_after = len([call for call in core.calls if call[0] == "GET"])
    assert first == second
    assert reads_after == reads_before  # повторное чтение — из кэша

    test_db.update_lead_funnel_state(user_id, conversation_stage="qualify", cta_shown=True)
    refreshed = test_db.get_lead_by_user_id(user_id)
    assert refreshed["conversation_stage"] == "qualify"
    assert refreshed["cta_shown"] == 1


def test_core_get_json_uses_short_cache(test_db, monkeypatch):
    import database as database_module

    calls = {"count": 0}

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(request, timeout=0):
        calls["count"] += 1
        return _FakeResponse([{"telegram_id": 424242, "username": "cached_core"}])

    monkeypatch.setattr(database_module.config, "CORE_API_SYNC_ENABLED", True)
    monkeypatch.setattr(database_module.config, "CORE_API_URL", "http://core-api:8000")
    monkeypatch.setattr(database_module.config, "API_KEY_BOT", "test-api-key")
    monkeypatch.setattr(database_module.config, "CORE_API_CACHE_TTL_SECONDS", 30.0)
    monkeypatch.setattr(database_module.config, "CORE_API_STALE_CACHE_TTL_SECONDS", 60.0)
    monkeypatch.setattr(database_module.urllib.request, "urlopen", _fake_urlopen)

    first = test_db._core_get_json("/api/v1/users", {"telegram_id": 424242})
    second = test_db._core_get_json("/api/v1/users", {"telegram_id": 424242})

    assert first == second
    assert calls["count"] == 1
