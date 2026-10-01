"""Переписка по делу: клиент из кабинета или бота ↔ юрист из рабочего места.

Закрепляется: клиент видит только свои дела; сообщение клиента попадает юристу
в «Задачи» и в уведомление без имени и текста; ответ юриста сохраняется всегда
(кабинет), клиенту с Telegram уходит ещё и туда с кнопкой «Ответить по делу»;
открыв переписку, сторона отмечает сообщения прочитанными; обезличивание
удаляет переписку.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from core_api import anonymization, telegram_delivery
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import CaseMessage, ClientNotice, ConflictCheckStatus, Lead, LeadSource, LegalIntake, Practice, Scope
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from test_practice import _cleanup, _key, _seed


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch):
    sent: list[dict] = []

    def fake_send(**kwargs):
        sent.append(kwargs)
        return {"message_id": 1}

    monkeypatch.setattr(telegram_delivery, "send", fake_send)
    monkeypatch.setattr(telegram_delivery, "_client_token", lambda: "test-token")
    names = [f"pytest.case-messages.bot.{uuid4().hex}", f"pytest.case-messages.admin.{uuid4().hex}"]
    bot = {"X-API-Key": _key(Scope.bot, names[0])}
    admin = {"X-API-Key": _key(Scope.admin, names[1])}
    own = _seed(practice=Practice.legal, conflict=ConflictCheckStatus.clear, nda=False)
    other = _seed(practice=Practice.legal, conflict=ConflictCheckStatus.clear, nda=False)
    yield {"client": TestClient(app), "bot": bot, "admin": admin, "own": own, "other": other, "sent": sent}
    db = SessionLocal()
    try:
        db.execute(delete(ClientNotice).where(ClientNotice.event_key.like("case-message:%")))
        db.commit()
    finally:
        db.close()
    _cleanup(names, own["lead_id"])
    _cleanup([], other["lead_id"])


def test_client_and_lawyer_exchange_messages(world) -> None:
    client, bot, admin, own = world["client"], world["bot"], world["admin"], world["own"]
    me = {"telegram_user_id": own["telegram_id"]}

    # Чужое дело по ссылке не открывается.
    alien = client.get(f"/api/v1/client-portal/cases/{world['other']['intake_id']}/messages", headers=bot, params=me)
    assert alien.status_code == 404

    written = client.post(f"/api/v1/client-portal/cases/{own['intake_id']}/messages", headers=bot,
                          json={**me, "text": "Пётр Петров: когда будет готов договор?", "channel": "telegram"})
    assert written.status_code == 201, written.text
    db = SessionLocal()
    try:
        notice = db.scalar(select(ClientNotice.text).where(ClientNotice.event_key == f"case-message:{written.json()['id']}"))
        # Уведомление юристу идёт через Telegram — без имени и текста клиента.
        assert notice and "Пётр" not in notice and "договор" not in notice
    finally:
        db.close()

    today = client.get("/api/v1/lawyer/today", headers=admin).json()
    section = next(s for s in today["sections"] if s["key"] == "client_messages")
    assert str(own["lead_id"]) in {item["lead_id"] for item in section["items"]}

    thread = client.get(f"/api/v1/lawyer/clients/{own['lead_id']}/messages", headers=admin).json()
    assert thread["client_has_telegram"] is True
    assert [m["author"] for m in thread["messages"]] == ["client"]
    # Юрист открыл переписку — сообщение клиента прочитано, из «Задач» ушло.
    today = client.get("/api/v1/lawyer/today", headers=admin).json()
    section = next(s for s in today["sections"] if s["key"] == "client_messages")
    assert str(own["lead_id"]) not in {item["lead_id"] for item in section["items"]}

    reply = client.post(f"/api/v1/lawyer/clients/{own['lead_id']}/messages", headers=admin,
                        json={"text": "Договор пришлю завтра.", "intake_id": own["intake_id"]})
    assert reply.status_code == 201, reply.text
    assert reply.json()["delivered"] == ["cabinet", "telegram"]
    sent = world["sent"][-1]
    assert sent["chat_id"] == own["telegram_id"] and "Договор пришлю завтра." in sent["text"]
    assert f"case:{own['intake_id']}" in sent["reply_markup"]

    summary = client.get("/api/v1/client-portal/summary", headers=bot, params=me).json()
    case = next(c for c in summary["cases"] if c["id"] == own["intake_id"])
    assert case["messages_unread"] == 1
    mine = client.get(f"/api/v1/client-portal/cases/{own['intake_id']}/messages", headers=bot, params=me).json()
    assert [m["author"] for m in mine["messages"]] == ["client", "lawyer"]
    summary = client.get("/api/v1/client-portal/summary", headers=bot, params=me).json()
    assert next(c for c in summary["cases"] if c["id"] == own["intake_id"])["messages_unread"] == 0


def test_reply_to_client_without_telegram_goes_to_cabinet(world) -> None:
    client, admin = world["client"], world["admin"]
    db = SessionLocal()
    try:
        lead = Lead(source=LeadSource.website_form, name="Без Телеграма", contact=f"nt-{uuid4().hex[:6]}@example.com")
        db.add(lead)
        db.flush()
        intake = LegalIntake(lead_id=lead.id, description="Вопрос по аренде офиса без Telegram.",
                             conflict_status=ConflictCheckStatus.clear, practice=Practice.legal)
        db.add(intake)
        db.commit()
        lead_id, intake_id = lead.id, intake.id
    finally:
        db.close()
    try:
        before = len(world["sent"])
        reply = client.post(f"/api/v1/lawyer/clients/{lead_id}/messages", headers=admin, json={"text": "Посмотрю завтра."})
        assert reply.status_code == 201, reply.text
        assert reply.json()["delivered"] == ["cabinet"]
        assert reply.json()["intake_id"] == str(intake_id)  # последнее дело клиента
        assert len(world["sent"]) == before
    finally:
        _cleanup([], lead_id)


def test_anonymization_removes_the_thread(world) -> None:
    client, bot, own = world["client"], world["bot"], world["own"]
    me = {"telegram_user_id": own["telegram_id"]}
    client.post(f"/api/v1/client-portal/cases/{own['intake_id']}/messages", headers=bot, json={**me, "text": "Мой телефон +7 900 000-00-00"})
    db = SessionLocal()
    try:
        lead = db.get(Lead, own["lead_id"])
        counts = anonymization.anonymize_lead(db, lead, datetime.now(timezone.utc))
        db.commit()
        assert counts["messages"] == 1
        assert db.scalar(select(func.count()).select_from(CaseMessage).where(CaseMessage.lead_id == own["lead_id"])) == 0
    finally:
        db.close()
