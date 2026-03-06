"""
Тесты для database.py - проверка работы с базой данных
"""
import pytest
import tempfile
import os
import time
from database import Database


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


def test_create_lead(test_db):
    """Проверка создания лида"""
    # Создаем пользователя
    user_id = test_db.create_or_update_user(
        telegram_id=123456789,
        username="testuser",
        first_name="Test"
    )

    # Создаем лид
    lead_data = {
        'name': 'Test Lead',
        'email': 'test@example.com',
        'temperature': 'hot'
    }
    lead_id = test_db.create_or_update_lead(user_id, lead_data)

    assert lead_id > 0, "Лид не создан"

    # Проверяем что лид сохранен
    lead = test_db.get_lead_by_user_id(user_id)
    assert lead is not None, "Лид не найден"
    assert lead['name'] == 'Test Lead'
    assert lead['email'] == 'test@example.com'
    assert lead['temperature'] == 'hot'


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


def test_consent_flow_and_data_export(test_db):
    """Проверка цикла согласия/экспорта/отзыва согласия."""
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

    cleanup = test_db.revoke_user_consent_and_delete_data(user_id)
    assert cleanup["users_updated"] == 1
    assert cleanup["messages_deleted"] >= 1

    lead_after = test_db.get_lead_by_user_id(user_id)
    assert lead_after["email"] is None
    assert lead_after["phone"] is None


def test_get_successful_conversations_returns_grouped_messages(test_db):
    """RAG-выборка должна возвращать диалоги без потери сообщений."""
    first_user_id = test_db.create_or_update_user(
        telegram_id=10001,
        username="rag_user_1",
        first_name="Rag",
    )
    second_user_id = test_db.create_or_update_user(
        telegram_id=10002,
        username="rag_user_2",
        first_name="RagTwo",
    )

    test_db.create_or_update_lead(
        first_user_id,
        {
            "name": "Rag User 1",
            "temperature": "warm",
            "service_category": "contracts",
            "pain_point": "Долго согласуем договоры",
        },
    )
    test_db.create_or_update_lead(
        second_user_id,
        {
            "name": "Rag User 2",
            "temperature": "hot",
            "service_category": "claims",
            "pain_point": "Большой поток претензий",
        },
    )

    test_db.add_message(first_user_id, "user", "Первое сообщение")
    test_db.add_message(first_user_id, "assistant", "Ответ ассистента")
    test_db.add_message(second_user_id, "user", "Второе сообщение")

    result = test_db.get_successful_conversations(limit=10)

    assert len(result) == 2
    by_user = {item["user_id"]: item for item in result}
    assert [msg["message"] for msg in by_user[first_user_id]["messages"]] == [
        "Первое сообщение",
        "Ответ ассистента",
    ]
    assert [msg["message"] for msg in by_user[second_user_id]["messages"]] == [
        "Второе сообщение",
    ]


def test_set_core_lead_id_persists_mapping(test_db):
    user_id = test_db.create_or_update_user(
        telegram_id=10003,
        username="core_sync_user",
        first_name="Core",
    )
    lead_id = test_db.create_or_update_lead(
        user_id,
        {
            "name": "Core Sync",
            "temperature": "warm",
        },
    )

    test_db.set_core_lead_id(lead_id, "11111111-1111-1111-1111-111111111111")

    lead = test_db.get_lead_by_id(lead_id)
    assert lead["core_lead_id"] == "11111111-1111-1111-1111-111111111111"


def test_reset_user_to_new_state_keeps_profile_and_clears_data(test_db):
    user_id = test_db.create_or_update_user(
        telegram_id=10005,
        username="reset_user",
        first_name="Reset",
        last_name="Candidate",
    )
    test_db.grant_user_consent(user_id)
    test_db.set_user_transborder_consent(user_id, True)
    test_db.create_or_update_lead(
        user_id,
        {
            "name": "Reset Candidate",
            "email": "reset@example.com",
            "phone": "+79001234567",
        },
    )
    test_db.add_message(user_id, "user", "старое сообщение")
    test_db.track_event(user_id, "stage_changed", payload={"from": "discover", "to": "diagnose"})

    result = test_db.reset_user_to_new_state(user_id)
    assert result["users_reset"] == 1
    assert result["leads_deleted"] >= 1
    assert result["messages_deleted"] >= 1
    assert result["events_deleted"] >= 1

    user = test_db.get_user_by_id(user_id)
    assert user is not None
    assert bool(user["consent_given"]) is False
    assert bool(user["transborder_consent"]) is False
    assert user["conversation_stage"] == "discover"
    assert test_db.get_lead_by_user_id(user_id) is None
    assert test_db.get_conversation_history(user_id) == []


def test_delete_user_completely_removes_profile_and_related_data(test_db):
    user_id = test_db.create_or_update_user(
        telegram_id=10006,
        username="delete_user",
        first_name="Delete",
        last_name="Candidate",
    )
    test_db.create_or_update_lead(
        user_id,
        {
            "name": "Delete Candidate",
            "email": "delete@example.com",
        },
    )
    test_db.add_message(user_id, "user", "какой-то диалог")
    test_db.track_event(user_id, "cta_clicked", payload={"variant": "a"})

    result = test_db.delete_user_completely(user_id)
    assert result["users_deleted"] == 1
    assert result["leads_deleted"] >= 1
    assert result["messages_deleted"] >= 1
    assert result["events_deleted"] >= 1

    assert test_db.get_user_by_id(user_id) is None
    assert test_db.get_user_by_telegram_id(10006) is None


def test_create_or_update_lead_syncs_to_core_bridge(test_db, monkeypatch):
    user_id = test_db.create_or_update_user(
        telegram_id=10004,
        username="bridge_user",
        first_name="Bridge",
    )

    class StubBridge:
        enabled = True

        @staticmethod
        def sync_lead(lead, user):
            assert lead["user_id"] == user_id
            assert user["telegram_id"] == 10004
            return "22222222-2222-2222-2222-222222222222"

    import core_api_bridge

    monkeypatch.setattr(core_api_bridge, "core_api_bridge", StubBridge())

    lead_id = test_db.create_or_update_lead(
        user_id,
        {
            "name": "Bridge Lead",
            "temperature": "warm",
            "pain_point": "Нужен sync в core-api",
        },
    )

    lead = test_db.get_lead_by_id(lead_id)
    assert lead["core_lead_id"] == "22222222-2222-2222-2222-222222222222"


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


def test_get_lead_by_user_id_prefers_core_snapshot(test_db, monkeypatch):
    user_id = test_db.create_or_update_user(
        telegram_id=10007,
        username="lead_local",
        first_name="Lead",
    )
    lead_id = test_db.create_or_update_lead(
        user_id,
        {
            "name": "Local Lead",
            "company": "Local Co",
            "temperature": "cold",
        },
    )

    def _fake_core(path, params=None):
        if path == "/api/v1/users" and params and params.get("telegram_id") == 10007:
            return [{"telegram_id": 10007, "username": "lead_local"}]
        if path == "/api/v1/leads" and params and params.get("legacy_lead_id") == lead_id:
            return [
                {
                    "id": "core-lead-10007",
                    "name": "Core Lead",
                    "company": "Core Co",
                    "temperature": "hot",
                    "status": "qualified",
                    "lead_magnet_delivered": True,
                }
            ]
        return None

    monkeypatch.setattr(test_db, "_core_get_json", _fake_core)

    lead = test_db.get_lead_by_user_id(user_id)

    assert lead is not None
    assert lead["name"] == "Core Lead"
    assert lead["company"] == "Core Co"
    assert lead["temperature"] == "hot"
    assert lead["core_lead_id"] == "core-lead-10007"
