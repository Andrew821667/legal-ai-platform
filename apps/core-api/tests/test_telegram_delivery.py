"""Отправка из ядра в Telegram больше не падает молча.

Закрепляется: у каждой отправки есть исход в журнале, даже если запрос юриста
упал с 502; фоновые уведомления повторяются и при исчерпании попыток видны в
«Не доставлено»; пропавшая связь доходит до владельца через бота, один раз.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from core_api import telegram_delivery
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ClientNotice, Scope, ServiceHealth, TelegramDelivery
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_client_archive import _cleanup, _key, _seed

TOKEN = "123456:SECRET-token_value"


@pytest.fixture(autouse=True)
def tokens(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LEAD_NOTIFY_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("LEAD_BOT_TOKEN", TOKEN)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    db = SessionLocal()
    try:
        db.execute(delete(TelegramDelivery).where(TelegramDelivery.kind.like("pytest%")))
        db.execute(delete(ServiceHealth))
        db.execute(delete(ClientNotice).where(ClientNotice.event_key.like("telegram_%")))
        db.commit()
    finally:
        db.close()


def _ok(token, chat_id, text, **kwargs):
    return {"message_id": 77}


def _boom(token, chat_id, text, **kwargs):
    # requests кладёт в текст ошибки адрес с токеном — в журнал он попасть не должен.
    raise TimeoutError(f"HTTPSConnectionPool: /bot{TOKEN}/sendMessage timed out")


def _row(kind="pytest_notice"):
    db = SessionLocal()
    try:
        stmt = select(TelegramDelivery).where(TelegramDelivery.kind == kind)
        return db.scalars(stmt.order_by(TelegramDelivery.created_at.desc())).first()
    finally:
        db.close()


def test_success_is_recorded_with_message_id() -> None:
    telegram_delivery.send(kind="pytest_notice", token=TOKEN, chat_id=1, text="привет", transport=_ok)
    row = _row()
    assert row.status == "sent"
    assert row.message_id == 77
    assert row.attempts == 1


def test_background_failure_waits_for_retry_and_hides_the_token() -> None:
    with pytest.raises(TimeoutError):
        telegram_delivery.send(
            kind="pytest_notice", token=TOKEN, chat_id=1, text="привет", retryable=True, transport=_boom
        )
    row = _row()
    assert row.status == "pending"
    assert row.next_attempt_at is not None
    assert "SECRET" not in row.last_error
    assert "bot<token>" in row.last_error


def test_retries_send_it_and_give_up_after_the_last_attempt() -> None:
    with pytest.raises(TimeoutError):
        telegram_delivery.send(
            kind="pytest_notice", token=TOKEN, chat_id=1, text="раз", retryable=True, transport=_boom
        )
    db = SessionLocal()
    try:
        row = db.scalars(select(TelegramDelivery).where(TelegramDelivery.kind == "pytest_notice")).one()
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        delivery_id = row.id
    finally:
        db.close()
    assert telegram_delivery.process_due(transport=_ok)["sent"] == 1
    assert _row().status == "sent"

    # Второе уведомление, которое так и не уходит: после последней попытки — failed.
    with pytest.raises(TimeoutError):
        telegram_delivery.send(
            kind="pytest_notice2", token=TOKEN, chat_id=1, text="два", retryable=True, transport=_boom
        )
    for _ in range(telegram_delivery.MAX_ATTEMPTS):
        db = SessionLocal()
        try:
            row = db.scalars(select(TelegramDelivery).where(TelegramDelivery.kind == "pytest_notice2")).one()
            if row.status != "pending":
                break
            row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        finally:
            db.close()
        telegram_delivery.process_due(transport=_boom)
    assert _row(kind="pytest_notice2").status == "failed"
    assert delivery_id


def test_failed_agreement_delivery_is_in_the_journal_and_on_the_task_screen(monkeypatch) -> None:
    """Запрос юриста падает с 502, а запись о сбое остаётся — и видна в задачах."""
    import core_api.routers.service_agreements as router

    monkeypatch.setattr(router, "_post_telegram_message", _boom)
    client = TestClient(app)
    name = f"pytest.delivery.{uuid4().hex}"
    key = _key(Scope.admin, name)
    seeded = _seed(9_400_000_000 + int(uuid4().hex[:5], 16))
    headers = {"X-API-Key": key}
    db = SessionLocal()
    try:
        from core_api.models import ServiceAgreement, ServiceAgreementStatus

        draft = db.scalars(
            select(ServiceAgreement).where(ServiceAgreement.parent_agreement_id.is_not(None))
            .where(ServiceAgreement.lead_id == seeded["lead_id"])
        ).one()
        draft.status = ServiceAgreementStatus.draft
        draft.client_telegram_user_id = 9_400_000_001
        db.commit()
        draft_id = str(draft.id)
    finally:
        db.close()
    try:
        response = client.post(f"/api/v1/service-agreements/{draft_id}/deliver", headers=headers)
        assert response.status_code == 502
        db = SessionLocal()
        try:
            row = db.scalars(
                select(TelegramDelivery).where(TelegramDelivery.agreement_id == draft_id)
            ).one()
            assert row.status == "failed"
            assert row.retryable is False
        finally:
            db.close()

        today = client.get("/api/v1/lawyer/today", headers=headers).json()
        section = next(s for s in today["sections"] if s["key"] == "undelivered")
        item = next(i for i in section["items"] if i["delivery_id"] == str(row.id))
        assert item["kind_label"] == "Договор клиенту"
        assert item["lead_id"] == seeded["lead_id"]

        # Договор повтором из журнала не шлём — только из карточки.
        refused = client.post(f"/api/v1/lawyer/deliveries/{row.id}/retry", headers=headers)
        assert refused.status_code == 409
        hidden = client.post(f"/api/v1/lawyer/deliveries/{row.id}/dismiss", headers=headers)
        assert hidden.status_code == 200
        today = client.get("/api/v1/lawyer/today", headers=headers).json()
        section = next(s for s in today["sections"] if s["key"] == "undelivered")
        assert all(i["delivery_id"] != str(row.id) for i in section["items"])
    finally:
        _cleanup([name], [seeded["lead_id"]])


class _Response:
    def __init__(self, ok: bool = True):
        self._ok = ok

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"ok": self._ok}


def _notices() -> list[str]:
    db = SessionLocal()
    try:
        return list(db.scalars(select(ClientNotice.event_key).where(ClientNotice.event_key.like("telegram_%"))))
    finally:
        db.close()


def test_lost_link_reaches_the_owner_once_and_recovery_too() -> None:
    def down(*args, **kwargs):
        raise ConnectionError(f"proxy refused /bot{TOKEN}/getMe")

    first = telegram_delivery.check_health(http_get=down)
    assert first["ok"] is False
    assert "SECRET" not in (first["error"] or "")
    # Минута без связи — ещё не повод будить владельца.
    assert _notices() == []

    db = SessionLocal()
    try:
        row = db.get(ServiceHealth, telegram_delivery.HEALTH_KEY)
        row.failing_since = datetime.now(timezone.utc) - timedelta(minutes=11)
        db.commit()
    finally:
        db.close()
    telegram_delivery.check_health(http_get=down)
    telegram_delivery.check_health(http_get=down)
    down_notices = [key for key in _notices() if key.startswith("telegram_down:")]
    assert len(down_notices) == 1

    back = telegram_delivery.check_health(http_get=lambda *a, **k: _Response(True))
    assert back["ok"] is True
    assert any(key.startswith("telegram_up:") for key in _notices())


def test_no_retries_while_the_link_is_down(monkeypatch) -> None:
    """Долгий сбой прокси не должен сжечь попытки впустую."""
    called: list[bool] = []
    monkeypatch.setattr(telegram_delivery, "check_health", lambda: {"ok": False})
    monkeypatch.setattr(telegram_delivery, "process_due", lambda *a, **k: called.append(True) or {})
    result = telegram_delivery.tick()
    assert result["due"] == {"skipped": True}
    assert called == []
