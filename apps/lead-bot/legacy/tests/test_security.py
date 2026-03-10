import os
import tempfile

import pytest

from database import Database
from handlers.business import parse_business_operator_command
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


def test_private_callback_mismatch_can_be_allowlisted_without_quarantine(isolated_security_db):
    user_id = 901099
    manager = security.SecurityManager()

    decision = manager.evaluate_human_actor(
        user_id=user_id,
        chat_id=user_id + 1,
        chat_type="private",
        allow_private_sender_chat_mismatch=True,
        update_type="callback_query",
        update_id=15,
    )

    assert decision.allowed is True
    quarantined, _reason, _entry = manager.is_quarantined(user_id)
    assert quarantined is False


def test_trusted_business_operator_ids_include_admin_and_configured_ids(isolated_security_db, monkeypatch):
    monkeypatch.setattr(security.config, "ADMIN_TELEGRAM_ID", 901101)
    monkeypatch.setattr(security.config, "BUSINESS_OPERATOR_TELEGRAM_IDS", [901102, 901103])
    manager = security.SecurityManager()

    assert manager.is_trusted_business_operator(901101) is True
    assert manager.is_trusted_business_operator(901102) is True
    assert manager.is_trusted_business_operator(901103) is True
    assert manager.is_trusted_business_operator(999999) is False


def test_parse_business_operator_command_supports_consultation_and_personal_modes():
    assert parse_business_operator_command("/operator_consultation нужен созвон") == (
        "consultation",
        "нужен созвон",
    )
    assert parse_business_operator_command("/handoff") == ("consultation", "")
    assert parse_business_operator_command("/operator_personal срочно") == ("personal_request", "срочно")
    assert parse_business_operator_command("обычный текст") is None


def test_business_callback_actor_mismatch_is_soft_block_only(isolated_security_db):
    user_id = 901100
    manager = security.SecurityManager()

    decision = manager.register_business_callback_actor_mismatch(
        user_id=user_id,
        chat_id=user_id + 1,
        update_id=16,
        business_connection_id="bc-test-1",
    )

    assert decision.allowed is False
    assert decision.action == "blocked_soft"
    assert decision.reason_code == "business_callback_actor_mismatch"

    quarantined, _reason, _entry = manager.is_quarantined(user_id)
    assert quarantined is False

    incidents = isolated_security_db.list_security_incidents(limit=5, telegram_user_id=user_id)
    assert incidents
    assert incidents[0]["reason_code"] == "business_callback_actor_mismatch"


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


def test_document_with_allowed_extension_passes_even_without_mime(isolated_security_db):
    user_id = 901013
    manager = security.SecurityManager()

    decision = manager.check_non_text_gate(
        user_id=user_id,
        chat_id=user_id,
        message_kind="document",
        attachment={"file_name": "brief.docx", "file_size": 128_000},
        update_id=30,
    )

    assert decision.allowed is True


def test_document_with_disallowed_mime_is_blocked(isolated_security_db):
    user_id = 901014
    manager = security.SecurityManager()

    decision = manager.check_non_text_gate(
        user_id=user_id,
        chat_id=user_id,
        message_kind="document",
        attachment={
            "file_name": "payload.exe",
            "mime_type": "application/x-msdownload",
            "file_size": 32_768,
        },
        update_id=31,
    )

    assert decision.allowed is False
    assert decision.reason_code == "document_mime_not_allowed"

    incidents = isolated_security_db.list_security_incidents(limit=5, telegram_user_id=user_id)
    assert incidents
    assert incidents[0]["reason_code"] == "document_mime_not_allowed"


def test_oversized_photo_is_blocked(isolated_security_db):
    user_id = 901015
    manager = security.SecurityManager()

    decision = manager.check_non_text_gate(
        user_id=user_id,
        chat_id=user_id,
        message_kind="photo",
        attachment={"file_size": manager.PHOTO_MAX_BYTES + 1},
        update_id=32,
    )

    assert decision.allowed is False
    assert decision.reason_code == "photo_too_large"
