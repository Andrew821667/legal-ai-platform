from __future__ import annotations

import os
import tempfile

from database import Database
from lead_qualifier import LeadQualifier
from tests.fake_core import install as install_fake_core


def test_process_lead_data_skips_new_lead_without_contact() -> None:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        db = Database(db_path)
        qualifier = LeadQualifier(db)
        user_id = db.create_or_update_user(
            telegram_id=555001,
            username="no_contact",
            first_name="NoContact",
        )

        lead_id = qualifier.process_lead_data(
            user_id,
            {
                "pain_point": "Ничего не понял",
                "lead_temperature": "cold",
                "service_category": "legal_ops",
            },
        )

        assert lead_id is None
        assert db.get_lead_by_user_id(user_id) is None
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_process_lead_data_updates_existing_contacted_lead_without_new_contact(monkeypatch) -> None:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        db = Database(db_path)
        install_fake_core(monkeypatch, db)
        qualifier = LeadQualifier(db)
        user_id = db.create_or_update_user(
            telegram_id=555002,
            username="existing_contact",
            first_name="Existing",
        )
        existing_lead_id = db.create_or_update_lead(
            user_id,
            {
                "name": "Existing",
                "phone": "+79092330909",
                "temperature": "warm",
            },
        )

        lead_id = qualifier.process_lead_data(
            user_id,
            {
                "pain_point": "Теряются юридические запросы",
                "lead_temperature": "warm",
                "service_category": "legal_ops",
            },
        )

        lead = db.get_lead_by_user_id(user_id)
        assert lead_id == existing_lead_id
        assert lead is not None
        assert lead["phone"] == "+79092330909"
        assert lead["pain_point"] == "Теряются юридические запросы"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_described_legal_task_creates_lead_with_telegram_contact(monkeypatch) -> None:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        db = Database(db_path)
        install_fake_core(monkeypatch, db)
        qualifier = LeadQualifier(db)
        user_id = db.create_or_update_user(telegram_id=555003, username="tg_only", first_name="Анна")
        extracted = {
            "name": "Анна",
            "pain_point": "Арендодатель не возвращает залог по договору аренды",
            "lead_temperature": "warm",
        }

        # Без описанной задачи в Telegram — как раньше: без контакта лида нет.
        assert qualifier.process_lead_data(user_id, extracted) is None

        lead_id = qualifier.process_lead_data(user_id, extracted, telegram_contact=True)

        lead = db.get_lead_by_user_id(user_id)
        assert lead_id is not None and lead is not None
        assert lead["pain_point"] == extracted["pain_point"]
        assert "[CONTACT_MODE]" in (lead["notes"] or "")
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_telegram_contact_needs_a_described_task(monkeypatch) -> None:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        db = Database(db_path)
        install_fake_core(monkeypatch, db)
        qualifier = LeadQualifier(db)
        user_id = db.create_or_update_user(telegram_id=555004, username="hello", first_name="Гость")

        assert qualifier.process_lead_data(
            user_id, {"name": "Гость", "lead_temperature": "cold"}, telegram_contact=True
        ) is None
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_owner_hears_once_then_only_about_news() -> None:
    from lead_qualifier import owner_should_hear

    warm = {"lead_temperature": "warm", "pain_point": "Теряем заявки"}
    # Впервые — да.
    assert owner_should_hear(None, warm) is True
    assert owner_should_hear({"notification_sent": 0, "temperature": "warm"}, warm) is True
    # Уже уведомлён, ничего нового — нет (раньше «НОВЫЙ ЛИД» шёл после каждого сообщения).
    notified = {"notification_sent": 1, "temperature": "warm"}
    assert owner_should_hear(notified, warm) is False
    # Потеплел до hot или впервые оставил телефон — да.
    assert owner_should_hear(notified, {**warm, "lead_temperature": "hot"}) is True
    assert owner_should_hear(notified, {**warm, "phone": "+79990000000"}) is True
    assert owner_should_hear({**notified, "phone": "+79990000000"}, {**warm, "phone": "+79990000000"}) is False
    # Холодный без контакта — нет; с описанной задачей в Telegram — да.
    cold = {"lead_temperature": "cold", "pain_point": "Вопрос по разделу имущества"}
    assert owner_should_hear(None, cold) is False
    assert owner_should_hear(None, cold, telegram_contact=True) is True
