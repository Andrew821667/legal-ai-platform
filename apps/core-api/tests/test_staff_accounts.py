"""Аккаунты владельца практики — тест, а не клиенты.

Владелец проверяет клиентский путь со своих аккаунтов Telegram. Для системы
это не лиды: помечены «Тест», не идут в деньги, бот не пишет им первым,
уведомлений о новом лиде нет. Весь остальной путь — как у клиента.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import Lead, LeadSource, LegalIntake, LegalIntakeStatus, Scope
from core_api.staff import is_staff, staff_telegram_ids
from fastapi.testclient import TestClient

from test_client_archive import _agreement, _cleanup, _key

OWNER = 7_700_000_061
SECOND = 7_700_000_279


@pytest.fixture
def staff(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", str(OWNER))
    monkeypatch.setenv("LAWYER_TELEGRAM_IDS", f" {SECOND} ,")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _client(telegram_id: int | None, name: str) -> dict:
    db = SessionLocal()
    try:
        lead = Lead(
            name=name,
            contact="@x",
            telegram_user_id=telegram_id,
            source=LeadSource.telegram_bot,
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=1),
            temperature="hot",
        )
        db.add(lead)
        db.flush()
        intake = LegalIntake(
            lead_id=lead.id,
            description=f"{name}: проверка пометки тестового клиента.",
            status=LegalIntakeStatus.accepted,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add(intake)
        db.flush()
        db.add(_agreement(lead.id, intake.id, amount_minor=7_000_000))
        db.commit()
        return {"lead_id": str(lead.id), "intake_id": str(intake.id)}
    finally:
        db.close()


def test_both_owner_accounts_are_staff(staff) -> None:
    assert staff_telegram_ids() == {OWNER, SECOND}
    assert is_staff(SECOND)
    assert not is_staff(None)
    assert not is_staff(123)


def test_owner_account_is_a_test_not_a_client(staff) -> None:
    client = TestClient(app)
    admin_name = f"pytest.staff.{uuid4().hex}"
    bot_name = f"pytest.staff.bot.{uuid4().hex}"
    admin = _key(Scope.admin, admin_name)
    bot = _key(Scope.bot, bot_name)
    test = _client(SECOND, "Andrew")
    real = _client(8_800_000_000 + int(uuid4().hex[:5], 16), "Настоящий клиент")
    headers = {"X-API-Key": admin}
    try:
        rows = {row["lead_id"]: row for row in client.get("/api/v1/lawyer/clients?limit=200", headers=headers).json()}
        assert rows[test["lead_id"]]["is_test"] is True
        assert rows[real["lead_id"]]["is_test"] is False

        card = client.get(f"/api/v1/lawyer/clients/{test['lead_id']}", headers=headers).json()
        assert card["is_test"] is True

        finance = client.get("/api/v1/lawyer/finance", headers=headers).json()
        listed = {row["lead_id"] for row in finance["agreements"]}
        assert test["lead_id"] not in listed
        assert real["lead_id"] in listed

        outreach = client.get("/api/v1/legal-intakes/outreach/pending?delay_minutes=0&limit=50", headers={"X-API-Key": bot}).json()
        waiting = {row["intake_id"] for row in outreach}
        assert test["intake_id"] not in waiting
        assert real["intake_id"] in waiting

        pending = client.get("/api/v1/leads/notifications/pending?idle_minutes=1&limit=100", headers={"X-API-Key": bot}).json()
        notified = {row["id"] for row in pending}
        assert test["lead_id"] not in notified
        assert real["lead_id"] in notified
    finally:
        _cleanup([admin_name, bot_name], [test["lead_id"], real["lead_id"]])
