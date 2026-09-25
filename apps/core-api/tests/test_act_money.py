"""Деньги по актам: кто должен, кто просрочил, кто сказал «оплатил».

Закрепляется: неоплаченный акт после срока не пропадает из виду — он в
«Деньгах» и в задачах; напомнить клиенту можно, но не чаще раза в сутки и
не тому, кто уже сообщил об оплате.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import Scope, ServiceAgreement, WorkAct, WorkActStatus
from fastapi.testclient import TestClient
from sqlalchemy import select

from test_client_archive import _cleanup, _key, _seed


def _act(agreement: ServiceAgreement, status: WorkActStatus, *, sent_days_ago: float, amount: int, **extra) -> WorkAct:
    now = datetime.now(timezone.utc)
    return WorkAct(
        act_number=f"AC-TEST-{uuid4().hex[:8].upper()}",
        agreement_id=agreement.id,
        lead_id=agreement.lead_id,
        description_text="Подготовлено заявление",
        amount_minor=amount,
        status=status,
        sent_at=now - timedelta(days=sent_days_ago),
        **extra,
    )


@pytest.fixture
def money():
    telegram_id = 9_500_000_000 + int(uuid4().hex[:5], 16)
    seeded = _seed(telegram_id)
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        agreement = db.get(ServiceAgreement, seeded["agreement_id"])
        agreement.client_telegram_user_id = telegram_id
        overdue = _act(agreement, WorkActStatus.sent, sent_days_ago=10, amount=1_000_000)
        claimed = _act(agreement, WorkActStatus.claimed_paid, sent_days_ago=3, amount=2_000_000, claimed_paid_at=now)
        paid = _act(agreement, WorkActStatus.paid, sent_days_ago=2, amount=3_000_000, paid_at=now)
        fresh = _act(agreement, WorkActStatus.sent, sent_days_ago=1, amount=4_000_000)
        cancelled = _act(agreement, WorkActStatus.sent, sent_days_ago=30, amount=9_000_000, cancelled_at=now)
        db.add_all([overdue, claimed, paid, fresh, cancelled])
        db.commit()
        acts = {k: str(v.id) for k, v in dict(overdue=overdue, claimed=claimed, paid=paid, fresh=fresh, cancelled=cancelled).items()}
    finally:
        db.close()
    yield seeded, acts


def test_finance_shows_receivables_overdue_and_claims(money) -> None:
    seeded, acts = money
    client = TestClient(app)
    name = f"pytest.acts.{uuid4().hex}"
    headers = {"X-API-Key": _key(Scope.admin, name)}
    try:
        finance = client.get("/api/v1/lawyer/finance", headers=headers).json()["acts"]
        mine = {row["act_id"]: row for row in finance["open"]}
        # Ждут оплаты: просроченный, «оплатил» и свежий; оплаченный и отозванный — нет.
        assert {acts["overdue"], acts["claimed"], acts["fresh"]} <= set(mine)
        assert acts["paid"] not in mine and acts["cancelled"] not in mine
        assert mine[acts["overdue"]]["overdue"] is True
        assert mine[acts["fresh"]]["overdue"] is False
        assert mine[acts["claimed"]]["overdue"] is False
        assert finance["overdue"]["minor"] >= 1_000_000
        assert finance["paid_this_month"]["minor"] >= 3_000_000

        today = client.get("/api/v1/lawyer/today", headers=headers).json()
        sections = {s["key"]: s for s in today["sections"]}
        assert acts["overdue"] in {i["act_id"] for i in sections["act_overdue"]["items"]}
        assert acts["claimed"] in {i["act_id"] for i in sections["act_claimed_paid"]["items"]}
        assert acts["fresh"] not in {i["act_id"] for i in sections["act_overdue"]["items"]}
    finally:
        _cleanup([name], [seeded["lead_id"]])


def test_reminder_once_a_day_and_not_to_who_said_paid(money, monkeypatch) -> None:
    import core_api.routers.work_acts as router

    sent: list[dict] = []

    def _send(token, chat_id, text, **kwargs):
        sent.append({"chat_id": chat_id, "text": text, **kwargs})
        return {"message_id": 1}

    monkeypatch.setattr(router, "_post_telegram_message", _send)
    monkeypatch.setattr(router, "_client_bot_token", lambda: "token")
    seeded, acts = money
    client = TestClient(app)
    name = f"pytest.acts.remind.{uuid4().hex}"
    headers = {"X-API-Key": _key(Scope.admin, name)}
    try:
        first = client.post(f"/api/v1/work-acts/{acts['overdue']}/remind", headers=headers)
        assert first.status_code == 200, first.text
        assert "Напоминаем об оплате" in sent[0]["text"]
        assert "act_c:claim:" in sent[0]["reply_markup"]

        again = client.post(f"/api/v1/work-acts/{acts['overdue']}/remind", headers=headers)
        assert again.status_code == 409
        told_paid = client.post(f"/api/v1/work-acts/{acts['claimed']}/remind", headers=headers)
        assert told_paid.status_code == 409
        assert len(sent) == 1

        db = SessionLocal()
        try:
            assert db.get(WorkAct, acts["overdue"]).last_reminded_at is not None
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            for act in db.scalars(select(WorkAct).where(WorkAct.lead_id == seeded["lead_id"])):
                db.delete(act)
            db.commit()
        finally:
            db.close()
        _cleanup([name], [seeded["lead_id"]])
