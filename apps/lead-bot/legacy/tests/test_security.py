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
