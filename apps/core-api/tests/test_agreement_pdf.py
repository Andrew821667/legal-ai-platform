"""PDF договора: точный текст и лист сведений о подписании; доступ — как у документа."""

from __future__ import annotations

from uuid import uuid4

from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import Scope, ServiceAgreement, ServiceAgreementStatus
from core_api.routers.service_agreements import _certificate_rows
from core_api.service_agreement import document_hash
from fastapi.testclient import TestClient

from test_agreement_supplements import _cleanup, _key, _seed


def _make_exact(agreement_id: str) -> None:
    """Засеянный текст — «текст»; сумму делаем честной, как у настоящего договора."""
    db = SessionLocal()
    try:
        item = db.get(ServiceAgreement, agreement_id)
        item.document_text = "ДОГОВОР ВОЗМЕЗДНОГО ОКАЗАНИЯ ЮРИДИЧЕСКИХ УСЛУГ № 1\n\n1. Стороны\nИсполнитель и Заказчик."
        item.document_hash = document_hash(item.document_text)
        item.signer_full_name = "Рябова Алёна Игоревна"
        item.signer_telegram_user_id = item.client_telegram_user_id
        item.signer_telegram_username = "ryabova"
        db.commit()
    finally:
        db.close()


def test_pdf_has_the_text_and_the_signing_sheet() -> None:
    client = TestClient(app)
    admin_name = f"pytest.pdf.{uuid4().hex}"
    bot_name = f"pytest.pdf.bot.{uuid4().hex}"
    admin = _key(Scope.admin, admin_name)
    bot = _key(Scope.bot, bot_name)
    seeded = _seed()
    _make_exact(seeded["agreement_id"])
    try:
        response = client.get(f"/api/v1/service-agreements/{seeded['agreement_id']}/pdf", headers={"X-API-Key": admin})
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")
        assert f'dogovor-{seeded["number"]}.pdf' in response.headers["content-disposition"]

        db = SessionLocal()
        try:
            rows = dict(_certificate_rows(db, db.get(ServiceAgreement, seeded["agreement_id"])))
        finally:
            db.close()
        assert rows["Текст совпадает с суммой"] == "да"
        assert rows["Подписант"] == "Рябова Алёна Игоревна"
        assert rows["Аккаунт Telegram"] == "@ryabova"
        assert rows["Подписан"].endswith("МСК")

        # Клиент — только свой документ.
        own = client.get(
            f"/api/v1/service-agreements/{seeded['agreement_id']}/pdf?telegram_user_id={seeded['telegram_id']}",
            headers={"X-API-Key": bot},
        )
        assert own.status_code == 200
        other = client.get(
            f"/api/v1/service-agreements/{seeded['agreement_id']}/pdf?telegram_user_id=1",
            headers={"X-API-Key": bot},
        )
        assert other.status_code == 403
    finally:
        _cleanup([admin_name, bot_name], seeded["lead_id"])


def test_client_does_not_get_a_draft_and_a_changed_text_is_flagged() -> None:
    client = TestClient(app)
    bot_name = f"pytest.pdf.draft.{uuid4().hex}"
    bot = _key(Scope.bot, bot_name)
    seeded = _seed(status=ServiceAgreementStatus.draft)
    try:
        hidden = client.get(
            f"/api/v1/service-agreements/{seeded['agreement_id']}/pdf?telegram_user_id={seeded['telegram_id']}",
            headers={"X-API-Key": bot},
        )
        assert hidden.status_code == 404
        db = SessionLocal()
        try:
            rows = dict(_certificate_rows(db, db.get(ServiceAgreement, seeded["agreement_id"])))
        finally:
            db.close()
        # В засеянном договоре сумма не от текста — лист это честно показывает.
        assert rows["Текст совпадает с суммой"].startswith("НЕТ")
        assert rows["Подписан"] == "не подписан"
    finally:
        _cleanup([bot_name], seeded["lead_id"])
