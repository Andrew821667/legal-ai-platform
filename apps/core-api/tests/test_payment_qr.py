"""Платёжный QR акта (ГОСТ Р 56042): что в нём и кому его показывают."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from core_api import payment_qr
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import Scope, ServiceAgreement, WorkAct, WorkActStatus
from core_api.routers.work_acts import _act_markup, payment_details
from fastapi.testclient import TestClient
from sqlalchemy import select

from test_client_archive import _cleanup, _key, _seed

REQUISITES = {
    "LAWYER_PAYMENT_ACCOUNT": "4081 7810 0000 0000 0001",
    "LAWYER_PAYMENT_BIC": "044525974",
    "LAWYER_PAYMENT_CORR_ACCOUNT": "30101810145250000974",
    "LAWYER_PAYMENT_BANK": "АО «ТБанк» | Москва",
    "LAWYER_PAYMENT_RECIPIENT": "Попов Андрей",
    "LAWYER_PAYMENT_INN": "123456789012",
    "LAWYER_PAYMENT_ACCOUNT_HOLDER": "",
    "LAWYER_PAYMENT_PURPOSE_PREFIX": "",
}


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch):
    for key, value in REQUISITES.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def unconfigured(monkeypatch: pytest.MonkeyPatch):
    for key in REQUISITES:
        monkeypatch.setenv(key, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_payload_is_st00012_with_sum_in_kopecks(configured) -> None:
    data = payment_qr.payload(1_500_000, "Оплата по акту № AC-1 к договору № AV-1")
    assert data == (
        "ST00012|Name=Попов Андрей|PersonalAcc=40817810000000000001|BankName=АО «ТБанк» Москва"
        "|BIC=044525974|CorrespAcc=30101810145250000974|PayeeINN=123456789012"
        "|Sum=1500000|Purpose=Оплата по акту № AC-1 к договору № AV-1"
    )
    assert payment_details()["qr"] is True
    assert "act_c:qr:" in _act_markup("x")


def test_without_account_there_is_no_qr(unconfigured) -> None:
    assert payment_qr.requisites() is None
    assert payment_qr.payload(100, "x") is None
    assert "act_c:qr:" not in _act_markup("x")


def _act(status: WorkActStatus) -> tuple[dict, str]:
    telegram_id = 9_600_000_000 + int(uuid4().hex[:5], 16)
    seeded = _seed(telegram_id)
    db = SessionLocal()
    try:
        agreement = db.get(ServiceAgreement, seeded["agreement_id"])
        act = WorkAct(
            act_number=f"AC-QR-{uuid4().hex[:6].upper()}",
            agreement_id=agreement.id,
            lead_id=agreement.lead_id,
            description_text="Работа",
            amount_minor=1_500_000,
            status=status,
            sent_at=datetime.now(timezone.utc),
        )
        agreement.client_telegram_user_id = telegram_id
        db.add(act)
        db.commit()
        return {**seeded, "telegram_id": telegram_id}, str(act.id)
    finally:
        db.close()


def _drop(seeded: dict) -> None:
    db = SessionLocal()
    try:
        for act in db.scalars(select(WorkAct).where(WorkAct.lead_id == seeded["lead_id"])):
            db.delete(act)
        db.commit()
    finally:
        db.close()


def test_client_gets_a_png_only_for_own_unpaid_act(configured) -> None:
    client = TestClient(app)
    name = f"pytest.qr.{uuid4().hex}"
    bot = {"X-API-Key": _key(Scope.bot, name)}
    seeded, act_id = _act(WorkActStatus.sent)
    paid_seeded, paid_id = _act(WorkActStatus.paid)
    try:
        own = client.get(f"/api/v1/work-acts/{act_id}/payment-qr?telegram_user_id={seeded['telegram_id']}", headers=bot)
        assert own.status_code == 200, own.text
        assert own.headers["content-type"] == "image/png"
        assert own.content.startswith(b"\x89PNG")
        other = client.get(f"/api/v1/work-acts/{act_id}/payment-qr?telegram_user_id=1", headers=bot)
        # Чужой акт — «не найден»: не выдаём, что он вообще есть.
        assert other.status_code == 404
        paid = client.get(f"/api/v1/work-acts/{paid_id}/payment-qr?telegram_user_id={paid_seeded['telegram_id']}", headers=bot)
        assert paid.status_code == 409
    finally:
        _drop(seeded)
        _drop(paid_seeded)
        _cleanup([name], [seeded["lead_id"], paid_seeded["lead_id"]])


def test_no_account_no_qr_endpoint(unconfigured) -> None:
    client = TestClient(app)
    name = f"pytest.qr.none.{uuid4().hex}"
    admin = {"X-API-Key": _key(Scope.admin, name)}
    seeded, act_id = _act(WorkActStatus.sent)
    try:
        assert client.get(f"/api/v1/work-acts/{act_id}/payment-qr", headers=admin).status_code == 404
    finally:
        _drop(seeded)
        _cleanup([name], [seeded["lead_id"]])


def test_account_holder_and_bank_purpose_prefix(configured, monkeypatch) -> None:
    """Полное имя как в банке и начало назначения, которое просит банк получателя."""
    monkeypatch.setenv("LAWYER_PAYMENT_ACCOUNT_HOLDER", "Попов Андрей Викторович")
    monkeypatch.setenv("LAWYER_PAYMENT_PURPOSE_PREFIX", "Перевод средств по договору № 111 Попов Андрей Викторович.")
    get_settings.cache_clear()
    data = payment_qr.payload(100, "Оплата по акту № AC-1")
    assert "|Name=Попов Андрей Викторович|" in data
    assert data.endswith("|Purpose=Перевод средств по договору № 111 Попов Андрей Викторович. Оплата по акту № AC-1")
