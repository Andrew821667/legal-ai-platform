"""Клиент без Telegram: учётная запись (Яндекс ID) и доступ к своим делам.

Закрепляется: вход через Яндекс заводит одну учётную запись и не сливает
чужую; по почте видны только дела с сайта (без Telegram) — дело из Telegram с
той же почтой в контактах чужому не открывается; подпись и приёмка без
Telegram пока недоступны (до новой редакции п.6 NDA), остальное работает.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ClientAccount,
    Lead,
    LeadSource,
    LegalIntake,
    LegalIntakeStatus,
    Scope,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)
from fastapi.testclient import TestClient
from sqlalchemy import delete

from test_client_archive import _agreement, _cleanup, _key


@pytest.fixture
def world():
    email = f"client-{uuid4().hex[:8]}@yandex.ru"
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        site = Lead(name="С сайта", contact=email, source=LeadSource.website_form)
        telegram = Lead(
            name="Из Telegram", contact=email, telegram_user_id=9_050_000_000 + int(uuid4().hex[:4], 16),
            source=LeadSource.telegram_bot,
        )
        db.add_all([site, telegram])
        db.flush()
        intake = LegalIntake(lead_id=site.id, description="Дело с сайта.", status=LegalIntakeStatus.accepted)
        db.add(intake)
        db.flush()
        own = _agreement(site.id, intake.id, status=ServiceAgreementStatus.viewed, signed_at=None, sent_at=now,
                         viewed_at=now, client_snapshot={"details_complete": True, "full_name": "Анна"})
        foreign = _agreement(telegram.id, None, status=ServiceAgreementStatus.sent, signed_at=None, sent_at=now,
                             client_telegram_user_id=telegram.telegram_user_id)
        db.add_all([own, foreign])
        db.flush()
        paid_ready = _agreement(site.id, intake.id)  # подписанный — для акта
        db.add(paid_ready)
        db.flush()
        act = WorkAct(act_number=f"AC-ACC-{uuid4().hex[:6].upper()}", agreement_id=paid_ready.id, lead_id=site.id,
                      description_text="Консультация", amount_minor=1_000_000, status=WorkActStatus.sent,
                      sent_at=now, document_text="АКТ", document_hash="d" * 64)
        db.add(act)
        db.commit()
        ids = {"site": str(site.id), "telegram": str(telegram.id), "own": str(own.id), "foreign": str(foreign.id),
               "own_hash": own.document_hash, "act": str(act.id)}
    finally:
        db.close()
    name = f"pytest.accounts.{uuid4().hex}"
    yield {"email": email, "ids": ids, "bot": {"X-API-Key": _key(Scope.bot, name)}}
    db = SessionLocal()
    try:
        db.execute(delete(ClientAccount).where(ClientAccount.email == email))
        db.commit()
    finally:
        db.close()
    _cleanup([name], [ids["site"], ids["telegram"]])


def _login(client, bot, email, yandex_id="ya-1"):
    return client.post("/api/v1/client-auth/yandex", json={"yandex_id": yandex_id, "email": email, "display_name": "Анна"}, headers=bot)


def test_yandex_login_keeps_one_account_and_does_not_merge_another(world) -> None:
    client = TestClient(app)
    first = _login(client, world["bot"], world["email"].upper())
    assert first.status_code == 200
    account_id = first.json()["client_account_id"]
    assert first.json()["email"] == world["email"]
    assert _login(client, world["bot"], world["email"]).json()["client_account_id"] == account_id
    # Та же почта, но другой аккаунт Яндекса — молча не сливаем.
    assert _login(client, world["bot"], world["email"], yandex_id="ya-2").status_code == 409


def test_account_sees_only_its_site_cases(world) -> None:
    client = TestClient(app)
    account_id = _login(client, world["bot"], world["email"]).json()["client_account_id"]
    summary = client.get(f"/api/v1/client-portal/summary?client_account_id={account_id}", headers=world["bot"]).json()
    assert summary["client"]["via"] == "account"
    assert summary["client"]["lead_id"] == world["ids"]["site"]
    agreement_ids = {a["id"] for a in summary["agreements"]}
    assert world["ids"]["own"] in agreement_ids
    # Дело из Telegram с той же почтой в контактах — не его.
    assert world["ids"]["foreign"] not in agreement_ids

    own = client.get(f"/api/v1/service-agreements/{world['ids']['own']}?client_account_id={account_id}", headers=world["bot"])
    assert own.status_code == 200
    foreign = client.get(f"/api/v1/service-agreements/{world['ids']['foreign']}?client_account_id={account_id}", headers=world["bot"])
    assert foreign.status_code == 403


def test_account_can_ask_but_cannot_sign_yet(world) -> None:
    client = TestClient(app)
    account_id = _login(client, world["bot"], world["email"]).json()["client_account_id"]
    agreement = world["ids"]["own"]
    asked = client.post(f"/api/v1/service-agreements/{agreement}/questions",
                        json={"text": "А сроки?", "client_account_id": account_id, "channel": "miniapp"}, headers=world["bot"])
    assert asked.status_code == 201
    signed = client.post(f"/api/v1/service-agreements/{agreement}/sign",
                         json={"client_account_id": account_id, "document_hash": world["ids"]["own_hash"],
                               "callback_id": "cab-1", "channel": "miniapp"}, headers=world["bot"])
    assert signed.status_code == 409
    assert "without Telegram" in signed.json()["detail"]


def test_account_opens_its_act_and_reports_payment(world) -> None:
    client = TestClient(app)
    account_id = _login(client, world["bot"], world["email"]).json()["client_account_id"]
    act = world["ids"]["act"]
    document = client.get(f"/api/v1/work-acts/{act}/document?client_account_id={account_id}", headers=world["bot"])
    assert document.status_code == 200
    claimed = client.post(f"/api/v1/work-acts/{act}/claim-paid",
                          json={"client_account_id": account_id, "channel": "miniapp"}, headers=world["bot"])
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "claimed_paid"


def test_request_without_any_client_is_rejected(world) -> None:
    client = TestClient(app)
    response = client.get("/api/v1/client-portal/summary", headers=world["bot"])
    assert response.status_code == 400
    unknown = client.get(f"/api/v1/client-portal/summary?client_account_id={uuid4()}", headers=world["bot"])
    assert unknown.status_code == 401
