"""Автонапоминание о неподписанном договоре.

Закрепляется: ядро напоминает само, но не больше двух раз, только днём и не
тому, кто ждёт ответа юриста или убран в архив; второе напоминание называет
дату окончания предложения; без связи с Telegram напоминаний нет.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from core_api import agreement_reminders, telegram_delivery
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    AuditLog,
    Lead,
    LeadSource,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
    ServiceAgreementStatus,
)
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_client_archive import _agreement, _cleanup, _key

TOKEN = "123456:SECRET-token_value"
# Полдень по Москве: напоминать можно.
NOON = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)


@pytest.fixture(autouse=True)
def tokens(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LEAD_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("LEAD_NOTIFY_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("AGREEMENT_REMIND_AFTER_DAYS", "3")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def seeded():
    created: list[str] = []

    def make(**kwargs) -> dict:
        telegram_id = 9_500_000_000 + int(uuid4().hex[:5], 16)
        db = SessionLocal()
        try:
            lead = Lead(name="Напоминание", contact="@test", telegram_user_id=telegram_id, source=LeadSource.telegram_bot)
            db.add(lead)
            db.flush()
            values = dict(
                status=ServiceAgreementStatus.sent,
                signed_at=None,
                client_telegram_user_id=telegram_id,
                sent_at=NOON - timedelta(days=4),
                expires_at=NOON + timedelta(days=3),
            )
            values.update(kwargs)
            item = _agreement(lead.id, None, **values)
            db.add(item)
            db.commit()
            created.append(str(lead.id))
            return {"lead_id": lead.id, "agreement_id": item.id, "chat_id": telegram_id}
        finally:
            db.close()

    yield make
    db = SessionLocal()
    try:
        ids = db.scalars(select(ServiceAgreement.id).where(ServiceAgreement.lead_id.in_(created))).all()
        if ids:
            db.execute(delete(AuditLog).where(AuditLog.target_id.in_(ids)))
            db.commit()
    finally:
        db.close()
    _cleanup([], created)


class _Capture:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def __call__(self, token, chat_id, text, **kwargs):
        self.sent.append({"chat_id": str(chat_id), "text": text, **kwargs})
        return {"message_id": 1}

    def to(self, chat_id: int) -> list[dict]:
        return [m for m in self.sent if m["chat_id"] == str(chat_id)]


def _agreement_row(agreement_id) -> ServiceAgreement:
    db = SessionLocal()
    try:
        return db.get(ServiceAgreement, agreement_id)
    finally:
        db.close()


def _update(agreement_id, **values) -> None:
    db = SessionLocal()
    try:
        row = db.get(ServiceAgreement, agreement_id)
        for key, value in values.items():
            setattr(row, key, value)
        db.commit()
    finally:
        db.close()


def test_first_reminder_after_silence_goes_once_with_the_same_buttons(seeded) -> None:
    case = seeded()
    capture = _Capture()
    agreement_reminders.process_due(now=NOON, transport=capture)
    messages = capture.to(case["chat_id"])
    assert len(messages) == 1
    assert "ждёт вашего решения" in messages[0]["text"]
    assert "Заполните свои реквизиты" in messages[0]["text"]
    buttons = json.loads(messages[0]["reply_markup"])["inline_keyboard"]
    assert buttons[0][0]["callback_data"] == f"sa_c:open:{case['agreement_id']}"

    row = _agreement_row(case["agreement_id"])
    assert row.reminders_sent == 1
    assert row.last_reminded_at is not None

    # Следующий такт — тишина: до последних суток предложения ещё далеко.
    again = _Capture()
    agreement_reminders.process_due(now=NOON + timedelta(minutes=2), transport=again)
    assert again.to(case["chat_id"]) == []


def test_last_call_names_the_date_and_there_is_no_third(seeded) -> None:
    expires = NOON + timedelta(hours=20)
    case = seeded(expires_at=expires)
    _update(case["agreement_id"], reminders_sent=1, last_reminded_at=NOON - timedelta(days=2))
    capture = _Capture()
    agreement_reminders.process_due(now=NOON, transport=capture)
    messages = capture.to(case["chat_id"])
    assert len(messages) == 1
    expected = expires.astimezone(agreement_reminders.MSK).strftime("%d.%m")
    assert f"действует до {expected}" in messages[0]["text"]
    assert _agreement_row(case["agreement_id"]).reminders_sent == 2

    third = _Capture()
    agreement_reminders.process_due(now=NOON + timedelta(hours=3), transport=third)
    assert third.to(case["chat_id"]) == []


def test_not_at_night(seeded) -> None:
    case = seeded()
    capture = _Capture()
    night = NOON.replace(hour=20)  # 23:00 МСК
    assert agreement_reminders.process_due(now=night, transport=capture) == {"skipped": "night"}
    assert _agreement_row(case["agreement_id"]).reminders_sent == 0


def test_not_while_the_client_waits_for_the_lawyer(seeded) -> None:
    case = seeded()
    db = SessionLocal()
    try:
        db.add(
            ServiceAgreementMessage(
                agreement_id=case["agreement_id"],
                role=ServiceAgreementMessageRole.client,
                telegram_user_id=case["chat_id"],
                text="А что входит в сопровождение?",
            )
        )
        db.commit()
    finally:
        db.close()
    capture = _Capture()
    agreement_reminders.process_due(now=NOON, transport=capture)
    assert capture.to(case["chat_id"]) == []

    # Юрист ответил — ход снова за клиентом.
    db = SessionLocal()
    try:
        db.add(
            ServiceAgreementMessage(
                agreement_id=case["agreement_id"],
                role=ServiceAgreementMessageRole.lawyer,
                text="Проверка документов и переговоры.",
                created_at=datetime.now(timezone.utc) + timedelta(seconds=1),
            )
        )
        db.commit()
    finally:
        db.close()
    agreement_reminders.process_due(now=NOON, transport=capture)
    assert len(capture.to(case["chat_id"])) == 1


@pytest.mark.parametrize(
    "values",
    [
        {"status": ServiceAgreementStatus.signed, "signed_at": NOON},
        {"status": ServiceAgreementStatus.declined},
        {"sent_at": NOON - timedelta(days=1)},
        {"expires_at": NOON - timedelta(hours=1)},
        {"client_telegram_user_id": None},
    ],
    ids=["signed", "declined", "too-early", "expired", "no-telegram"],
)
def test_nothing_to_remind(seeded, values) -> None:
    case = seeded(**values)
    capture = _Capture()
    agreement_reminders.process_due(now=NOON, transport=capture)
    assert capture.to(case["chat_id"]) == []
    assert _agreement_row(case["agreement_id"]).reminders_sent == 0


def test_not_for_an_archived_client(seeded) -> None:
    case = seeded()
    db = SessionLocal()
    try:
        db.get(Lead, case["lead_id"]).archived_at = NOON
        db.commit()
    finally:
        db.close()
    capture = _Capture()
    agreement_reminders.process_due(now=NOON, transport=capture)
    assert capture.to(case["chat_id"]) == []


def test_can_be_turned_off(seeded, monkeypatch) -> None:
    seeded()
    monkeypatch.setenv("AGREEMENT_REMIND_AFTER_DAYS", "0")
    get_settings.cache_clear()
    assert agreement_reminders.process_due(now=NOON, transport=_Capture()) == {"skipped": "disabled"}


def test_failed_reminder_is_in_the_journal_and_not_repeated(seeded) -> None:
    case = seeded()

    def boom(*args, **kwargs):
        raise TimeoutError("proxy timed out")

    assert agreement_reminders.process_due(now=NOON, transport=boom)["failed"] >= 1
    db = SessionLocal()
    try:
        from core_api.models import TelegramDelivery

        row = db.scalars(
            select(TelegramDelivery).where(TelegramDelivery.agreement_id == case["agreement_id"])
        ).one()
        assert row.kind == "agreement_reminder"
        assert row.status == "failed"
        assert row.retryable is False
    finally:
        db.close()
    capture = _Capture()
    agreement_reminders.process_due(now=NOON + timedelta(minutes=2), transport=capture)
    assert capture.to(case["chat_id"]) == []


def test_tick_skips_reminders_without_a_link(monkeypatch) -> None:
    called: list[bool] = []
    monkeypatch.setattr(
        telegram_delivery, "tick", lambda: {"health": {"ok": False}, "due": {"skipped": True}}
    )
    monkeypatch.setattr(agreement_reminders, "process_due", lambda *a, **k: called.append(True) or {})
    name = f"pytest.remind.{uuid4().hex}"
    key = _key(Scope.bot, name)
    try:
        response = TestClient(app).post("/api/v1/telegram/tick", headers={"X-API-Key": key})
        assert response.status_code == 200
        assert response.json()["agreement_reminders"] == {"skipped": "no_link"}
        assert called == []
    finally:
        _cleanup([name], [])
