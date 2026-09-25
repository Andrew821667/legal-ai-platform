"""Чек самозанятого по оплаченному акту.

Закрепляется: оплаченный акт без чека виден в «Сегодня»; чек записывается
только для оплаченного акта; отправить клиенту можно только ссылку — тем же
ботом, и отправка остаётся в журнале.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import Scope, ServiceAgreement, TelegramDelivery, WorkAct, WorkActStatus
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_client_archive import _cleanup, _key, _seed

LINK = "https://lknpd.nalog.ru/api/v1/receipt/683302758241/200abc/print"


@pytest.fixture
def acts(monkeypatch: pytest.MonkeyPatch):
    import core_api.routers.work_acts as router

    sent: list[dict] = []

    def fake(token, chat_id, text, **kwargs):
        sent.append({"chat_id": str(chat_id), "text": text})
        return {"message_id": 5}

    monkeypatch.setattr(router, "_post_telegram_message", fake)
    monkeypatch.setenv("LEAD_BOT_TOKEN", "123:abc")
    from core_api.config import get_settings

    get_settings.cache_clear()
    telegram_id = 9_300_000_000 + int(uuid4().hex[:5], 16)
    seeded = _seed(telegram_id)
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        agreement = db.get(ServiceAgreement, seeded["agreement_id"])
        agreement.client_telegram_user_id = telegram_id

        def act(status: WorkActStatus, **extra) -> WorkAct:
            row = WorkAct(
                act_number=f"AC-RC-{uuid4().hex[:6].upper()}", agreement_id=agreement.id, lead_id=agreement.lead_id,
                description_text="Консультация", amount_minor=1_500_000, status=status, sent_at=now, **extra,
            )
            db.add(row)
            return row

        paid = act(WorkActStatus.paid, paid_at=now)
        paid_quiet = act(WorkActStatus.paid, paid_at=now)
        unpaid = act(WorkActStatus.sent)
        db.commit()
        ids = {"paid": str(paid.id), "paid_quiet": str(paid_quiet.id), "unpaid": str(unpaid.id)}
    finally:
        db.close()
    name = f"pytest.receipt.{uuid4().hex}"
    yield {"ids": ids, "sent": sent, "chat": str(telegram_id), "headers": {"X-API-Key": _key(Scope.admin, name)}}
    db = SessionLocal()
    try:
        db.execute(delete(TelegramDelivery).where(TelegramDelivery.act_id.in_(list(ids.values()))))
        db.commit()
    finally:
        db.close()
    get_settings.cache_clear()
    _cleanup([name], [seeded["lead_id"]])


def _missing(client, headers) -> set[str]:
    today = client.get("/api/v1/lawyer/today", headers=headers).json()
    section = next(s for s in today["sections"] if s["key"] == "receipt_missing")
    return {item["act_id"] for item in section["items"]}


def test_receipt_link_goes_to_the_client_and_task_disappears(acts) -> None:
    client = TestClient(app)
    ids, headers = acts["ids"], acts["headers"]
    assert {ids["paid"], ids["paid_quiet"]} <= _missing(client, headers)
    assert ids["unpaid"] not in _missing(client, headers)

    response = client.post(
        f"/api/v1/work-acts/{ids['paid']}/receipt", json={"ref": LINK, "send_to_client": True}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["receipt_ref"] == LINK and body["receipt_at"] and body["receipt_sent_at"]
    [message] = acts["sent"]
    assert message["chat_id"] == acts["chat"]
    assert LINK in message["text"] and "15 000" in message["text"]

    db = SessionLocal()
    try:
        row = db.scalars(select(TelegramDelivery).where(TelegramDelivery.act_id == ids["paid"])).one()
        assert row.kind == "receipt" and row.status == "sent"
    finally:
        db.close()
    assert ids["paid"] not in _missing(client, headers)


def test_receipt_without_link_is_recorded_but_not_sent(acts) -> None:
    client = TestClient(app)
    ids, headers = acts["ids"], acts["headers"]
    refused = client.post(
        f"/api/v1/work-acts/{ids['paid_quiet']}/receipt", json={"ref": "12345", "send_to_client": True}, headers=headers
    )
    assert refused.status_code == 422
    saved = client.post(f"/api/v1/work-acts/{ids['paid_quiet']}/receipt", json={}, headers=headers)
    assert saved.status_code == 200
    assert saved.json()["receipt_at"] and saved.json()["receipt_sent_at"] is None
    assert acts["sent"] == []
    assert ids["paid_quiet"] not in _missing(client, headers)


def test_receipt_only_for_a_paid_act(acts) -> None:
    client = TestClient(app)
    response = client.post(
        f"/api/v1/work-acts/{acts['ids']['unpaid']}/receipt", json={"ref": LINK}, headers=acts["headers"]
    )
    assert response.status_code == 409
