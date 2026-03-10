import os
import tempfile

import pytest

from database import Database
import security


@pytest.fixture
def isolated_security_db(monkeypatch):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_db = Database(db_path)
    monkeypatch.setattr(security.database, "db", test_db)
    try:
        yield test_db
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_rate_limit_persists_after_manager_restart(isolated_security_db):
    user_id = 901001
    manager = security.SecurityManager()

    for _ in range(manager.RATE_LIMITS["messages_per_minute"]):
        allowed, reason = manager.check_rate_limit(user_id)
        assert allowed is True
        assert reason is None

    blocked, block_reason = manager.check_rate_limit(user_id)
    assert blocked is False
    assert "Слишком много сообщений" in (block_reason or "")

    restarted_manager = security.SecurityManager()
    blocked_after_restart, _ = restarted_manager.check_rate_limit(user_id)
    assert blocked_after_restart is False


def test_token_usage_and_budget_persist_after_manager_restart(isolated_security_db):
    user_id = 901002
    manager = security.SecurityManager()
    manager.add_tokens_used(5000, user_id=user_id)

    restarted_manager = security.SecurityManager()

    allowed_user, _ = restarted_manager.check_token_limit(user_id, estimated_tokens=46000)
    assert allowed_user is False

    allowed_budget, budget_reason = restarted_manager.check_total_budget(estimated_tokens=96000)
    assert allowed_budget is False
    assert "дневной лимит" in (budget_reason or "")


def test_human_only_bot_actor_goes_to_quarantine_and_persists(isolated_security_db):
    user_id = 901010
    manager = security.SecurityManager()

    decision = manager.evaluate_human_actor(
        user_id=user_id,
        chat_id=user_id,
        chat_type="private",
        is_bot=True,
        update_type="message",
        update_id=1,
    )

    assert decision.allowed is False
    assert decision.action == "quarantine"
    entry = isolated_security_db.get_security_quarantine_entry(user_id)
    assert entry is not None
    assert entry["reason_code"] == "from_user_is_bot"

    restarted_manager = security.SecurityManager()
    quarantined, reason, persisted_entry = restarted_manager.is_quarantined(user_id)
    assert quarantined is True
    assert "подозрительная активность" in (reason or "").lower()
    assert persisted_entry is not None


def test_callback_duplicate_burst_triggers_quarantine(isolated_security_db, monkeypatch):
    user_id = 901011
    manager = security.SecurityManager()
    now = 1_800_000_000
    monkeypatch.setattr(security.time, "time", lambda: now)

    first = manager.check_callback_gate(
        user_id=user_id,
        chat_id=user_id,
        callback_data="admin_section_users",
        update_id=10,
    )
    second = manager.check_callback_gate(
        user_id=user_id,
        chat_id=user_id,
        callback_data="admin_section_users",
        update_id=11,
    )
    third = manager.check_callback_gate(
        user_id=user_id,
        chat_id=user_id,
        callback_data="admin_section_users",
        update_id=12,
    )

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.action == "quarantine"

    incidents = isolated_security_db.list_security_incidents(limit=5, telegram_user_id=user_id)
    assert incidents
    assert incidents[0]["reason_code"] == "callback_duplicate_burst"


def test_supported_non_text_is_allowed_and_quarantine_blocks_text_security(isolated_security_db):
    user_id = 901012
    manager = security.SecurityManager()

    allowed_non_text = manager.check_non_text_gate(
        user_id=user_id,
        chat_id=user_id,
        message_kind="document",
        update_id=20,
    )
    assert allowed_non_text.allowed is True

    manager.evaluate_human_actor(
        user_id=user_id,
        chat_id=user_id,
        chat_type="private",
        is_bot=True,
        update_type="message",
        update_id=21,
    )

    blocked, reason = manager.check_all_security(user_id, "Здравствуйте, нужен аудит договоров")
    assert blocked is False
    assert "подозрительная активность" in (reason or "").lower()
