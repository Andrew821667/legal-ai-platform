"""Отзывы клиентов после оплаченного акта.

Закрепляется: бот просит оценку один раз, через сутки после оплаты и днём;
оценить можно только свой оплаченный акт; на сайт попадает только отзыв с
согласием клиента и одобрением юриста, а новый текст снова ждёт решения.
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
from core_api.models import ClientNotice, Scope, ServiceAgreement, WorkAct, WorkActStatus
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_client_archive import _cleanup, _key, _seed

NOON = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)


@pytest.fixture
def paid(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LEAD_BOT_TOKEN", "123:abc")
    get_settings.cache_clear()
    telegram_id = 9_200_000_000 + int(uuid4().hex[:5], 16)
    seeded = _seed(telegram_id)
    db = SessionLocal()
    try:
        agreement = db.get(ServiceAgreement, seeded["agreement_id"])
        agreement.client_telegram_user_id = telegram_id

        def act(**extra) -> WorkAct:
            values = dict(
                act_number=f"AC-RV-{uuid4().hex[:6].upper()}", agreement_id=agreement.id, lead_id=agreement.lead_id,
                description_text="Консультация", amount_minor=1_000_000, status=WorkActStatus.paid,
                sent_at=NOON - timedelta(days=3), paid_at=NOON - timedelta(hours=30),
            )
            values.update(extra)
            row = WorkAct(**values)
            db.add(row)
            return row

        due = act()
        fresh = act(paid_at=NOON - timedelta(hours=2))
        cancelled = act(cancelled_at=NOON)
        unpaid = act(status=WorkActStatus.sent, paid_at=None)
        db.commit()
        ids = {k: str(v.id) for k, v in dict(due=due, fresh=fresh, cancelled=cancelled, unpaid=unpaid).items()}
    finally:
        db.close()
    name = f"pytest.reviews.{uuid4().hex}"
    yield {"ids": ids, "tg": telegram_id, "bot": {"X-API-Key": _key(Scope.bot, name)},
           "admin": {"X-API-Key": _key(Scope.admin, f"{name}.admin")}}
    db = SessionLocal()
    try:
        db.execute(delete(ClientNotice).where(ClientNotice.event_key.like("review_%")))
        db.commit()
    finally:
        db.close()
    get_settings.cache_clear()
    _cleanup([name, f"{name}.admin"], [seeded["lead_id"]])


class _Capture:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def __call__(self, token, chat_id, text, **kwargs):
        self.sent.append({"chat_id": str(chat_id), "text": text, **kwargs})
        return {"message_id": 1}


def test_request_once_a_day_after_payment_and_only_by_day(paid) -> None:
    capture = _Capture()
    client_reviews.process_due(now=NOON, transport=capture)
    mine = [m for m in capture.sent if m["chat_id"] == str(paid["tg"])]
    assert len(mine) == 1
    buttons = json.loads(mine[0]["reply_markup"])["inline_keyboard"][0]
    assert [b["callback_data"] for b in buttons] == [f"act_c:rv:{paid['ids']['due']}:{n}" for n in range(1, 6)]

    again = _Capture()
    client_reviews.process_due(now=NOON + timedelta(minutes=2), transport=again)
    assert [m for m in again.sent if m["chat_id"] == str(paid["tg"])] == []
    assert client_reviews.process_due(now=NOON.replace(hour=20), transport=_Capture()) == {"skipped": "night"}


def test_client_reviews_only_own_paid_act(paid) -> None:
    client = TestClient(app)
    due, bot = paid["ids"]["due"], paid["bot"]
    assert client.post(f"/api/v1/work-acts/{due}/review", json={"telegram_user_id": 1, "score": 5}, headers=bot).status_code == 404
    unpaid = paid["ids"]["unpaid"]
    assert client.post(
        f"/api/v1/work-acts/{unpaid}/review", json={"telegram_user_id": paid["tg"], "score": 5}, headers=bot
    ).status_code == 409
    assert client.post(
        f"/api/v1/work-acts/{due}/review", json={"telegram_user_id": paid["tg"], "score": 6}, headers=bot
    ).status_code == 422

    scored = client.post(f"/api/v1/work-acts/{due}/review", json={"telegram_user_id": paid["tg"], "score": 5}, headers=bot)
    assert scored.status_code == 200 and scored.json()["score"] == 5
    db = SessionLocal()
    try:
        keys = list(db.scalars(select(ClientNotice.event_key).where(ClientNotice.event_key.like("review_score:%"))))
    finally:
        db.close()
    assert len(keys) == 1


def test_publication_needs_consent_and_approval(paid) -> None:
    client = TestClient(app)
    due, bot, admin = paid["ids"]["due"], paid["bot"], paid["admin"]

    def post(body: dict) -> dict:
        response = client.post(f"/api/v1/work-acts/{due}/review", json={"telegram_user_id": paid["tg"], **body}, headers=bot)
        assert response.status_code == 200
        return response.json()

    def public_texts() -> list[str]:
        return [r["text"] for r in client.get("/api/v1/reviews/public", headers=bot).json()]

    review = post({"score": 5, "text": "Быстро разобрались с договором"})
    assert review["status"] == "pending"
    rid = review["review_id"]

    # Без согласия клиента — не публикуется, даже если юрист хочет.
    assert client.post(f"/api/v1/lawyer/reviews/{rid}/approve", headers=admin).status_code == 409

    post({"publish_consent": True})
    today = client.get("/api/v1/lawyer/today", headers=admin).json()
    section = next(s for s in today["sections"] if s["key"] == "review_moderation")
    assert rid in {i["review_id"] for i in section["items"]}
    assert "Быстро разобрались с договором" not in public_texts()

    assert client.post(f"/api/v1/lawyer/reviews/{rid}/approve", headers=admin).json()["status"] == "approved"
    assert "Быстро разобрались с договором" in public_texts()

    # Клиент переписал текст — снова ждёт решения и с сайта уходит.
    assert post({"text": "Быстро и понятно"})["status"] == "pending"
    assert "Быстро и понятно" not in public_texts()

    card = client.get(f"/api/v1/lawyer/clients/{review_lead(due)}", headers=admin).json()
    acts = [a for agreement in card["agreements"] for a in agreement["acts"]]
    assert next(a for a in acts if a["act_id"] == due)["review"]["score"] == 5


def review_lead(act_id: str) -> str:
    db = SessionLocal()
    try:
        return str(db.get(WorkAct, act_id).lead_id)
    finally:
        db.close()
