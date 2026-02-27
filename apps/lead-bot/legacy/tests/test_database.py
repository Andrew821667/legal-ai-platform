"""
Тесты для database.py - проверка работы с базой данных
"""
import pytest
import tempfile
import os
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
