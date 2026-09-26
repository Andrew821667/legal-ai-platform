"""Запись на платную консультацию.

Закрепляется весь путь: юрист открывает время; клиент бронирует его вместе с
обращением (занятое — 409 и ни клиента, ни обращения); платит по QR и
сообщает об оплате; юрист подтверждает — доход идёт в лимит НПД, в
«Задачах» остаётся чек; неоплаченная бронь сгорает сама; снятая бронь
возвращает время; закрыть занятое время нельзя.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from core_api import consultations, npd_limit
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ClientNotice, ConsultationSlot, Lead, LegalIntake, Scope
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from test_practice import _cleanup, _key


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch):
    from core_api.routers import legal_intakes

    monkeypatch.setattr(legal_intakes, "notify_new_legal_intake", lambda *_: None)
    names = [f"pytest.consult.admin.{uuid4().hex}", f"pytest.consult.bot.{uuid4().hex}"]
    client = TestClient(app)
    admin = {"X-API-Key": _key(Scope.admin, names[0])}
    bot = {"X-API-Key": _key(Scope.bot, names[1])}
    # Время в пределах публичного окна (21 день), в своей минуте.
    base = (datetime.now(timezone.utc) + timedelta(days=15)).replace(second=0, microsecond=0)
    base = base.replace(minute=int(uuid4().hex[:2], 16) % 60)
    opened = client.post("/api/v1/lawyer/consultations/slots", headers=admin, json={
        "starts_at": [base.isoformat(), (base + timedelta(hours=2)).isoformat(),
                      (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()],
        "duration_min": 60,
    })
    assert opened.status_code == 200, opened.text
    slots = [row["slot_id"] for row in opened.json()["created"]]
    assert opened.json()["skipped"] == 1  # прошедшее время не открывается
    yield {"client": client, "admin": admin, "bot": bot, "slots": slots, "base": base}
    db = SessionLocal()
    try:
        lead_ids = list(db.scalars(select(ConsultationSlot.lead_id).where(ConsultationSlot.id.in_(slots))))
        lead_ids += list(db.scalars(select(Lead.id).where(Lead.contact.like("consult-%@example.com"))))
        db.execute(delete(ConsultationSlot).where(ConsultationSlot.id.in_(slots)))
        db.execute(delete(ClientNotice).where(ClientNotice.event_key.like("consultation-claim:%")))
        db.commit()
    finally:
        db.close()
    for lead_id in {lead for lead in lead_ids if lead}:
        _cleanup([], lead_id)
    _cleanup(names, None)
    get_settings.cache_clear()


def _book(world, slot_id, contact=None):
    return world["client"].post("/api/v1/legal-intakes", headers=world["bot"], json={
        "source": "website_form",
        "name": "Анна",
        "contact": contact or f"consult-{uuid4().hex[:8]}@example.com",
        "description": "Нужна консультация по договору аренды офиса.",
        "consent_accepted": True, "consent_version": "test", "consent_at": "2026-09-26T00:00:00Z",
        "package_id": "legal_consultation", "package_title": "Консультация юриста", "package_price_text": "4 900 ₽",
        "consultation_slot_id": slot_id,
    })


def test_booking_pay_confirm_and_receipt(world) -> None:
    client, admin, bot = world["client"], world["admin"], world["bot"]
    free = client.get("/api/v1/consultations/slots", headers=bot).json()
    assert free["price_minor"] == 490_000
    assert set(world["slots"]) <= {s["slot_id"] for s in free["slots"]}

    booked = _book(world, world["slots"][0])
    assert booked.status_code == 201, booked.text
    consultation = booked.json()["consultation"]
    assert consultation["status"] == "held" and consultation["code"].startswith("K-")
    token = consultation["access_token"]

    # Второй клиент на то же время — 409, и никто не создан.
    db = SessionLocal()
    before = db.scalar(select(func.count()).select_from(Lead))
    db.close()
    taken = _book(world, world["slots"][0])
    assert taken.status_code == 409 and taken.json()["detail"] == "Consultation slot is taken"
    db = SessionLocal()
    assert db.scalar(select(func.count()).select_from(Lead)) == before
    db.close()
    assert world["slots"][0] not in {s["slot_id"] for s in client.get("/api/v1/consultations/slots", headers=bot).json()["slots"]}

    page = client.get(f"/api/v1/consultations/bookings/{token}", headers=bot).json()
    assert page["status"] == "held" and page["price_minor"] == 490_000
    claimed = client.post(f"/api/v1/consultations/bookings/{token}/claim", headers=bot).json()
    assert claimed["status"] == "claimed"
    db = SessionLocal()
    try:
        notice = db.scalar(select(ClientNotice.text).where(ClientNotice.event_key.like(f"consultation-claim:{world['slots'][0]}%")))
        assert consultation["code"] in notice
    finally:
        db.close()
    # После «оплатил» сам клиент бронь не отменит — это деньги, решает юрист.
    assert client.post(f"/api/v1/consultations/bookings/{token}/cancel", headers=bot).status_code == 409

    today = client.get("/api/v1/lawyer/today", headers=admin).json()
    claimed_section = next(s for s in today["sections"] if s["key"] == "consultation_claimed")
    assert world["slots"][0] in {i["slot_id"] for i in claimed_section["items"]}

    db = SessionLocal()
    income_before = npd_limit._income(db, npd_limit.year_start(datetime.now(timezone.utc)))
    db.close()
    confirmed = client.post(f"/api/v1/lawyer/consultations/{world['slots'][0]}/confirm", headers=admin)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    db = SessionLocal()
    assert npd_limit._income(db, npd_limit.year_start(datetime.now(timezone.utc))) == income_before + 490_000
    db.close()

    today = client.get("/api/v1/lawyer/today", headers=admin).json()
    receipt_section = next(s for s in today["sections"] if s["key"] == "consultation_receipt")
    assert world["slots"][0] in {i["slot_id"] for i in receipt_section["items"]}
    client.post(f"/api/v1/lawyer/consultations/{world['slots'][0]}/receipt", headers=admin,
                json={"ref": "https://lknpd.nalog.ru/api/v1/receipt/x"})
    today = client.get("/api/v1/lawyer/today", headers=admin).json()
    receipt_section = next(s for s in today["sections"] if s["key"] == "consultation_receipt")
    assert world["slots"][0] not in {i["slot_id"] for i in receipt_section["items"]}

    events = client.get("/api/v1/lawyer/calendar", headers=admin).json()["events"]
    event = next(e for e in events if e["uid"] == f"consultation-{world['slots'][0]}")
    assert event["duration_min"] == 60 and "Анна" not in event["title"]

    # Занятое время закрыть нельзя; снять бронь — время снова свободно.
    assert client.delete(f"/api/v1/lawyer/consultations/slots/{world['slots'][0]}", headers=admin).status_code == 409
    released = client.post(f"/api/v1/lawyer/consultations/{world['slots'][0]}/release", headers=admin).json()
    assert released["was"] == "confirmed"
    assert client.get(f"/api/v1/consultations/bookings/{token}", headers=bot).status_code == 404


def test_unpaid_hold_expires_and_client_can_cancel(world) -> None:
    client, bot = world["client"], world["bot"]
    booked = _book(world, world["slots"][1]).json()["consultation"]
    db = SessionLocal()
    try:
        slot = db.get(ConsultationSlot, world["slots"][1])
        slot.held_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    # Сгоревшая бронь: время свободно, страница брони — «не найдена».
    assert world["slots"][1] in {s["slot_id"] for s in client.get("/api/v1/consultations/slots", headers=bot).json()["slots"]}
    assert client.get(f"/api/v1/consultations/bookings/{booked['access_token']}", headers=bot).status_code == 404
    # Обращение клиента при этом остаётся — юрист видит, что человек приходил.
    db = SessionLocal()
    try:
        assert db.scalar(select(LegalIntake).where(LegalIntake.package_id == "legal_consultation",
                                                   LegalIntake.description.like("Нужна консультация%"))) is not None
    finally:
        db.close()

    again = _book(world, world["slots"][1]).json()["consultation"]
    cancelled = client.post(f"/api/v1/consultations/bookings/{again['access_token']}/cancel", headers=bot)
    assert cancelled.status_code == 200
    assert world["slots"][1] in {s["slot_id"] for s in client.get("/api/v1/consultations/slots", headers=bot).json()["slots"]}


def test_closed_time_can_be_reopened_and_duplicates_are_skipped(world) -> None:
    client, admin = world["client"], world["admin"]
    closed = client.delete(f"/api/v1/lawyer/consultations/slots/{world['slots'][1]}", headers=admin)
    assert closed.status_code == 200
    base = world["base"]
    reopened = client.post("/api/v1/lawyer/consultations/slots", headers=admin, json={
        "starts_at": [(base + timedelta(hours=2)).isoformat(), base.isoformat()]})
    assert reopened.status_code == 200
    # Закрытое время открылось заново, а уже открытое пропущено.
    assert len(reopened.json()["created"]) == 1 and reopened.json()["skipped"] == 1
    world["slots"].extend(row["slot_id"] for row in reopened.json()["created"])
    assert consultations.MOSCOW is not None
