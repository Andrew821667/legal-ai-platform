"""Запрос документов у клиента списком.

Закрепляется: юрист сохраняет список, клиент с Telegram получает сообщение
(сбой связи — повтор из журнала, список уже виден), без Telegram — список в
кабинете; повтор того же пункта не дублируется; загрузка в пункт закрывает
его, а чужой пункт — нет; отменённое клиенту не показывается.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from core_api import telegram_delivery
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    DocumentRequest,
    Lead,
    LeadSource,
    LegalIntake,
    LegalIntakeStatus,
    NdaSignature,
    Scope,
    TelegramDelivery,
)
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_practice import _cleanup, _key


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LEAD_BOT_TOKEN", "123:test-token")
    get_settings.cache_clear()
    sent: list[dict] = []

    def transport(token, chat_id, text, **kwargs):
        sent.append({"chat_id": chat_id, "text": text})
        return {"message_id": len(sent)}

    monkeypatch.setattr(telegram_delivery, "_default_transport", lambda: transport)
    telegram_id = 9_200_000_000 + int(uuid4().hex[:5], 16)
    email = f"docs-{uuid4().hex[:6]}@example.com"
    db = SessionLocal()
    try:
        tg = Lead(name="Из бота", contact="@docs", telegram_user_id=telegram_id, source=LeadSource.telegram_bot)
        site = Lead(name="С сайта", contact=email, source=LeadSource.website_form)
        silent = Lead(name="Без связи", contact="+7 900 000-00-02", source=LeadSource.website_form)
        db.add_all([tg, site, silent])
        db.flush()
        intakes = {}
        for key, lead in (("tg", tg), ("tg_other", tg), ("site", site), ("silent", silent)):
            intake = LegalIntake(lead_id=lead.id, description="Нужна помощь по делу.", status=LegalIntakeStatus.accepted)
            db.add(intake)
            db.flush()
            intakes[key] = str(intake.id)
        db.add(NdaSignature(lead_id=tg.id, telegram_user_id=telegram_id, document_version="t", document_hash="c" * 64))
        db.commit()
        leads = {"tg": str(tg.id), "site": str(site.id), "silent": str(silent.id)}
    finally:
        db.close()
    names = [f"pytest.docreq.{uuid4().hex}", f"pytest.docreq.bot.{uuid4().hex}"]
    yield {
        "sent": sent,
        "telegram_id": telegram_id,
        "email": email,
        "intakes": intakes,
        "leads": leads,
        "admin": {"X-API-Key": _key(Scope.admin, names[0])},
        "bot": {"X-API-Key": _key(Scope.bot, names[1])},
    }
    db = SessionLocal()
    try:
        db.execute(delete(TelegramDelivery).where(TelegramDelivery.lead_id.in_(leads.values())))
        db.commit()
    finally:
        db.close()
    for lead_id in leads.values():
        _cleanup([], lead_id)
    _cleanup(names, None)
    get_settings.cache_clear()


def _request(client, world, intake_key, titles, note=None):
    return client.post(
        f"/api/v1/lawyer/intakes/{world['intakes'][intake_key]}/document-requests",
        json={"titles": titles, "note": note},
        headers=world["admin"],
    )


def test_list_reaches_the_client_and_repeats_are_not_duplicated(world) -> None:
    client = TestClient(app)
    first = _request(client, world, "tg", ["Паспорт", "Договор аренды"], "Можно фото, главное — читаемо.")
    assert first.status_code == 200, first.text
    assert first.json()["delivered_via"] == "telegram"
    assert [r["title"] for r in first.json()["requests"]] == ["Паспорт", "Договор аренды"]
    message = world["sent"][0]
    assert message["chat_id"] == str(world["telegram_id"])
    assert "• Паспорт" in message["text"] and "• Договор аренды" in message["text"]
    assert "Можно фото" in message["text"]

    # «паспорт» уже ждём — добавится только переписка.
    second = _request(client, world, "tg", ["  паспорт ", "Переписка с арендодателем"])
    assert [r["title"] for r in second.json()["requests"]] == ["Переписка с арендодателем"]
    again = _request(client, world, "tg", ["Паспорт"])
    assert again.status_code == 409

    card = client.get(f"/api/v1/lawyer/clients/{world['leads']['tg']}", headers=world["admin"]).json()
    intake = next(i for i in card["intakes"] if i["intake_id"] == world["intakes"]["tg"])
    assert [r["status"] for r in intake["document_requests"]] == ["open", "open", "open"]


def test_upload_into_a_request_closes_it_but_not_someone_elses(world) -> None:
    client = TestClient(app)
    passport = _request(client, world, "tg", ["Паспорт"]).json()["requests"][0]
    other = _request(client, world, "tg_other", ["Выписка ЕГРН"]).json()["requests"][0]

    upload = client.post(
        f"/api/v1/legal-intakes/{world['intakes']['tg']}/documents",
        json={"telegram_user_id": world["telegram_id"], "telegram_file_id": "file-1",
              "file_name": "passport.pdf", "request_id": passport["request_id"]},
        headers=world["bot"],
    )
    assert upload.status_code == 200, upload.text
    # Пункт другого обращения этим файлом не закрывается.
    stray = client.post(
        f"/api/v1/legal-intakes/{world['intakes']['tg']}/documents",
        json={"telegram_user_id": world["telegram_id"], "telegram_file_id": "file-2",
              "file_name": "egrn.pdf", "request_id": other["request_id"]},
        headers=world["bot"],
    )
    assert stray.status_code == 200

    db = SessionLocal()
    try:
        done = db.get(DocumentRequest, passport["request_id"])
        assert done.status == "received" and done.document_id is not None and done.received_at is not None
        assert db.get(DocumentRequest, other["request_id"]).status == "open"
    finally:
        db.close()

    summary = client.get(
        f"/api/v1/client-portal/summary?telegram_user_id={world['telegram_id']}", headers=world["bot"]
    ).json()
    statuses = {
        r["title"]: r["status"] for case in summary["cases"] for r in case.get("document_requests", [])
    }
    assert statuses == {"Паспорт": "received", "Выписка ЕГРН": "open"}


def test_lawyer_marks_and_cancelled_is_hidden_from_the_client(world) -> None:
    client = TestClient(app)
    rows = _request(client, world, "tg", ["Доверенность", "Претензия"]).json()["requests"]
    cancelled = client.patch(
        f"/api/v1/lawyer/document-requests/{rows[0]['request_id']}", json={"status": "cancelled"}, headers=world["admin"]
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    received = client.patch(
        f"/api/v1/lawyer/document-requests/{rows[1]['request_id']}", json={"status": "received"}, headers=world["admin"]
    )
    assert received.json()["status"] == "received" and received.json()["document_id"] is None
    foreign_file = client.patch(
        f"/api/v1/lawyer/document-requests/{rows[1]['request_id']}",
        json={"status": "received", "document_id": str(uuid4())},
        headers=world["admin"],
    )
    assert foreign_file.status_code == 404

    summary = client.get(
        f"/api/v1/client-portal/summary?telegram_user_id={world['telegram_id']}", headers=world["bot"]
    ).json()
    titles = [r["title"] for case in summary["cases"] for r in case.get("document_requests", [])]
    assert titles == ["Претензия"]


def test_without_telegram_the_list_lives_in_the_cabinet(world) -> None:
    client = TestClient(app)
    site = _request(client, world, "site", ["Паспорт"]).json()
    assert site["delivered_via"] == "cabinet" and site["cabinet_email"] == world["email"]
    silent = _request(client, world, "silent", ["Паспорт"]).json()
    assert silent["delivered_via"] == "none"
    assert world["sent"] == []


def test_telegram_failure_keeps_the_list_and_retries(world, monkeypatch) -> None:
    def broken(token, chat_id, text, **kwargs):
        raise ConnectionError("proxy down")

    monkeypatch.setattr(telegram_delivery, "_default_transport", lambda: broken)
    client = TestClient(app)
    response = _request(client, world, "tg", ["Паспорт"])
    assert response.status_code == 200
    assert response.json()["delivered_via"] == "queued"
    db = SessionLocal()
    try:
        row = db.scalar(
            select(TelegramDelivery).where(
                TelegramDelivery.lead_id == world["leads"]["tg"], TelegramDelivery.kind == "document_request"
            )
        )
        assert row is not None and row.retryable and row.status != "sent"
        assert db.scalar(
            select(DocumentRequest).where(DocumentRequest.intake_id == world["intakes"]["tg"])
        ).status == "open"
    finally:
        db.close()


def test_without_bot_token_the_lawyer_is_told_so(world, monkeypatch) -> None:
    monkeypatch.setenv("LEAD_BOT_TOKEN", "")
    monkeypatch.setenv("LEAD_NOTIFY_BOT_TOKEN", "")
    get_settings.cache_clear()
    response = _request(TestClient(app), world, "tg", ["Паспорт"])
    assert response.json()["delivered_via"] == "not_configured"
    assert world["sent"] == []
