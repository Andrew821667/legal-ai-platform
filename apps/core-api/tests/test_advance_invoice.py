"""Счёт на предоплату (аванс) по договору.

Закрепляется: аванс создаётся без описания работ, уходит клиенту с QR и
«Я оплатил(а)», но без приёмки работы; принять или оспорить его нельзя;
отзыв по авансу не просят — оценивать ещё нечего.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from core_api import client_reviews
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import Scope, ServiceAgreement, TelegramDelivery, WorkAct, WorkActStatus
from fastapi.testclient import TestClient
from sqlalchemy import delete

from test_client_archive import _cleanup, _key, _seed


@pytest.fixture
def signed(monkeypatch: pytest.MonkeyPatch):
    import core_api.routers.work_acts as router

    sent: list[dict] = []

    def fake(token, chat_id, text, **kwargs):
        sent.append({"chat_id": str(chat_id), "text": text, **kwargs})
        return {"message_id": 3}

    monkeypatch.setattr(router, "_post_telegram_message", fake)
    monkeypatch.setenv("LEAD_BOT_TOKEN", "123:abc")
    get_settings.cache_clear()
    telegram_id = 9_100_500_000 + int(uuid4().hex[:4], 16)
    seeded = _seed(telegram_id)
    db = SessionLocal()
    try:
        db.get(ServiceAgreement, seeded["agreement_id"]).client_telegram_user_id = telegram_id
        db.commit()
    finally:
        db.close()
    name = f"pytest.advance.{uuid4().hex}"
    yield {"seeded": seeded, "tg": telegram_id, "sent": sent, "headers": {"X-API-Key": _key(Scope.admin, name)},
           "bot": {"X-API-Key": _key(Scope.bot, f"{name}.bot")}}
    db = SessionLocal()
    try:
        db.execute(delete(TelegramDelivery).where(TelegramDelivery.lead_id == seeded["lead_id"]))
        db.commit()
    finally:
        db.close()
    get_settings.cache_clear()
    _cleanup([name, f"{name}.bot"], [seeded["lead_id"]])


def test_advance_is_a_payment_document_without_acceptance(signed) -> None:
    client = TestClient(app)
    headers = signed["headers"]
    created = client.post(
        "/api/v1/work-acts",
        json={"agreement_id": signed["seeded"]["agreement_id"], "kind": "advance", "amount_minor": 3_000_000},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    advance = created.json()
    assert advance["kind"] == "advance"
    assert advance["act_number"].startswith("PP-")
    assert advance["description_text"].startswith("Предоплата по договору")

    assert client.post(f"/api/v1/work-acts/{advance['id']}/send", headers=headers).status_code == 200
    document = client.get(
        f"/api/v1/work-acts/{advance['id']}/document?telegram_user_id={signed['tg']}", headers=signed["bot"]
    ).json()
    assert document["text"].startswith("СЧЁТ НА ПРЕДОПЛАТУ")
    assert document["kind"] == "advance"
    [message] = signed["sent"]
    assert message["text"].startswith("Счёт на предоплату")
    callbacks = [b["callback_data"] for row in json.loads(message["reply_markup"])["inline_keyboard"] for b in row]
    assert f"act_c:claim:{advance['id']}" in callbacks
    assert not any(c.startswith("act_c:open:") for c in callbacks)

    # Принять работу по авансу нельзя — принимать нечего.
    viewed = client.post(
        f"/api/v1/work-acts/{advance['id']}/client/viewed",
        json={"telegram_user_id": signed["tg"], "document_hash": document["document_hash"], "callback_id": "cb1"},
        headers=signed["bot"],
    )
    assert viewed.status_code == 200
    accepted = client.post(
        f"/api/v1/work-acts/{advance['id']}/client/accept",
        json={"telegram_user_id": signed["tg"], "document_hash": document["document_hash"], "callback_id": "cb2"},
        headers=signed["bot"],
    )
    assert accepted.status_code == 409


def test_regular_act_still_requires_a_description(signed) -> None:
    response = TestClient(app).post(
        "/api/v1/work-acts",
        json={"agreement_id": signed["seeded"]["agreement_id"], "amount_minor": 1_000_000},
        headers=signed["headers"],
    )
    assert response.status_code == 422


def test_no_review_request_for_a_paid_advance(signed) -> None:
    now = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    db = SessionLocal()
    try:
        agreement = db.get(ServiceAgreement, signed["seeded"]["agreement_id"])
        advance = WorkAct(
            act_number=f"PP-TEST-{uuid4().hex[:6].upper()}", kind="advance", agreement_id=agreement.id,
            lead_id=agreement.lead_id, description_text="Предоплата", amount_minor=1_000_000,
            status=WorkActStatus.paid, sent_at=now - timedelta(days=2), paid_at=now - timedelta(hours=30),
        )
        db.add(advance)
        db.commit()
        advance_id = str(advance.id)
    finally:
        db.close()
    captured: list[dict] = []
    client_reviews.process_due(now=now, transport=lambda token, chat_id, text, **kw: captured.append(kw) or {"message_id": 1})
    assert not any(advance_id in str(kw.get("reply_markup")) for kw in captured)
