"""Файлы по делу в нашей базе: результат от юриста в кабинет, загрузки клиента из кабинета.

Закрепляется: содержимое в базе зашифровано; клиент скачивает только свои
файлы; в Telegram о файле — уведомление без имени файла, сам файл туда не
уходит; загрузка клиента — только после NDA, закрывает пункт «юрист просит»,
юристу — уведомление без имени; сводка кабинета показывает файлы, чеки и
консультации; обезличивание удаляет файлы.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from core_api import anonymization, telegram_delivery
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ClientFile,
    ClientNotice,
    ConflictCheckStatus,
    ConsultationSlot,
    DocumentRequest,
    Lead,
    Practice,
    Scope,
)
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from test_practice import _cleanup, _key, _seed

PDF = b"%PDF-1.4 test result of work"


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch):
    sent: list[dict] = []

    def fake_send(**kwargs):
        sent.append(kwargs)
        return {"message_id": 1}

    monkeypatch.setattr(telegram_delivery, "send", fake_send)
    monkeypatch.setattr(telegram_delivery, "_client_token", lambda: "test-token")
    names = [f"pytest.client-files.bot.{uuid4().hex}", f"pytest.client-files.admin.{uuid4().hex}"]
    bot = {"X-API-Key": _key(Scope.bot, names[0])}
    admin = {"X-API-Key": _key(Scope.admin, names[1])}
    own = _seed(practice=Practice.legal, conflict=ConflictCheckStatus.clear, nda=True)
    other = _seed(practice=Practice.legal, conflict=ConflictCheckStatus.clear, nda=True)
    unsigned = _seed(practice=Practice.legal, conflict=ConflictCheckStatus.clear, nda=False)
    yield {"client": TestClient(app), "bot": bot, "admin": admin, "own": own, "other": other,
           "unsigned": unsigned, "sent": sent}
    db = SessionLocal()
    try:
        db.execute(delete(ClientNotice).where(ClientNotice.event_key.like("client-file:%")))
        db.execute(delete(ConsultationSlot).where(ConsultationSlot.lead_id.in_(
            [own["lead_id"], other["lead_id"], unsigned["lead_id"]])))
        db.commit()
    finally:
        db.close()
    _cleanup(names, own["lead_id"])
    _cleanup([], other["lead_id"])
    _cleanup([], unsigned["lead_id"])


def test_lawyer_sends_result_to_cabinet(world) -> None:
    client, bot, admin, own = world["client"], world["bot"], world["admin"], world["own"]
    me = {"telegram_user_id": own["telegram_id"]}

    sent = client.post(
        f"/api/v1/lawyer/clients/{own['lead_id']}/files", headers=admin,
        data={"note": "Заключение по договору аренды."},
        files={"file": ("Заключение Петрову.pdf", PDF, "application/pdf")},
    )
    assert sent.status_code == 201, sent.text
    body = sent.json()
    assert body["delivered"] == ["cabinet", "telegram_notice"]
    assert body["intake_id"] == own["intake_id"]  # последнее дело клиента
    notice = world["sent"][-1]
    # В Telegram — только уведомление: без имени файла (в нём фамилия) и без самого файла.
    assert notice["chat_id"] == own["telegram_id"]
    assert "Петров" not in notice["text"] and "кабинете" in notice["text"]
    assert "/miniapp/cases" in notice["reply_markup"] and f"case:{own['intake_id']}" in notice["reply_markup"]

    db = SessionLocal()
    try:
        row = db.get(ClientFile, body["id"])
        assert row is not None and PDF not in row.content  # в базе — шифротекст
    finally:
        db.close()

    summary = client.get("/api/v1/client-portal/summary", headers=bot, params=me).json()
    case = next(c for c in summary["cases"] if c["id"] == own["intake_id"])
    assert [f["file_name"] for f in case["files"]] == ["Заключение Петрову.pdf"]
    # Файл виден и в переписке по делу — с пометкой юриста.
    assert case["messages_unread"] == 1

    # Чужой клиент файл по ссылке не получит.
    alien = client.get(f"/api/v1/client-portal/files/{body['id']}", headers=bot,
                       params={"telegram_user_id": world["other"]["telegram_id"]})
    assert alien.status_code == 404
    got = client.get(f"/api/v1/client-portal/files/{body['id']}", headers=bot, params=me)
    assert got.status_code == 200 and got.content == PDF
    assert "filename*=UTF-8''" in got.headers["content-disposition"]
    listed = client.get(f"/api/v1/lawyer/clients/{own['lead_id']}/files", headers=admin).json()["files"]
    assert listed[0]["downloaded_at"] is not None  # юрист видит, что клиент скачал


def test_client_uploads_to_database_not_telegram(world) -> None:
    client, bot, admin, own = world["client"], world["bot"], world["admin"], world["own"]
    me = {"telegram_user_id": str(own["telegram_id"])}
    db = SessionLocal()
    try:
        ask = DocumentRequest(intake_id=own["intake_id"], title="Договор аренды")
        db.add(ask)
        db.commit()
        request_id = str(ask.id)
    finally:
        db.close()

    before = len(world["sent"])
    up = client.post(
        f"/api/v1/client-portal/cases/{own['intake_id']}/files", headers=bot,
        data={**me, "request_id": request_id},
        files={"file": ("Аренда Петров.docx", b"PK docx bytes", "application/octet-stream")},
    )
    assert up.status_code == 201, up.text
    assert len(world["sent"]) == before  # в Telegram файл не уходил

    db = SessionLocal()
    try:
        notice = db.scalar(select(ClientNotice.text).where(ClientNotice.event_key == f"client-file:{up.json()['id']}"))
        assert notice and "Петров" not in notice
        assert db.get(DocumentRequest, request_id).status == "received"
    finally:
        db.close()

    got = client.get(f"/api/v1/lawyer/files/{up.json()['id']}", headers=admin)
    assert got.status_code == 200 and got.content == b"PK docx bytes"

    # Чужое дело, файл не из списка и NDA — те же условия, что в чате.
    alien = client.post(f"/api/v1/client-portal/cases/{world['other']['intake_id']}/files", headers=bot,
                        data=me, files={"file": ("a.pdf", PDF, "application/pdf")})
    assert alien.status_code == 404
    exe = client.post(f"/api/v1/client-portal/cases/{own['intake_id']}/files", headers=bot,
                      data=me, files={"file": ("run.exe", b"MZ", "application/octet-stream")})
    assert exe.status_code == 422
    unsigned = world["unsigned"]
    no_nda = client.post(f"/api/v1/client-portal/cases/{unsigned['intake_id']}/files", headers=bot,
                         data={"telegram_user_id": str(unsigned["telegram_id"])},
                         files={"file": ("a.pdf", PDF, "application/pdf")})
    assert no_nda.status_code == 409


def test_summary_shows_consultation_and_receipt(world) -> None:
    client, bot, own = world["client"], world["bot"], world["own"]
    db = SessionLocal()
    try:
        db.add(ConsultationSlot(status="confirmed", lead_id=own["lead_id"], price_minor=300000, code="K-TEST",
                                access_token=uuid4().hex, receipt_ref="https://lknpd.nalog.ru/api/v1/receipt/1/2/print",
                                receipt_at=datetime.now(timezone.utc)))
        db.commit()
    finally:
        db.close()
    summary = client.get("/api/v1/client-portal/summary", headers=bot,
                         params={"telegram_user_id": own["telegram_id"]}).json()
    [slot] = summary["consultations"]
    assert slot["status"] == "confirmed" and slot["starts_at"] is None  # время согласуем
    assert slot["receipt_ref"].startswith("https://lknpd.nalog.ru/")


def test_lawyer_deletes_and_anonymization_removes_files(world) -> None:
    client, admin, own = world["client"], world["admin"], world["own"]
    ids = [
        client.post(f"/api/v1/lawyer/clients/{own['lead_id']}/files", headers=admin,
                    files={"file": (f"v{n}.pdf", PDF, "application/pdf")}).json()["id"]
        for n in range(2)
    ]
    assert client.delete(f"/api/v1/lawyer/files/{ids[0]}", headers=admin).json() == {"deleted": True}
    assert client.get(f"/api/v1/lawyer/files/{ids[0]}", headers=admin).status_code == 404
    db = SessionLocal()
    try:
        lead = db.get(Lead, own["lead_id"])
        counts = anonymization.anonymize_lead(db, lead, datetime.now(timezone.utc))
        db.commit()
        assert counts["files"] == 1
        assert db.scalar(select(func.count()).select_from(ClientFile).where(ClientFile.lead_id == own["lead_id"])) == 0
    finally:
        db.close()
