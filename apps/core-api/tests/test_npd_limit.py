"""Годовой лимит самозанятого: доход за год и предупреждение владельцу.

Закрепляется: доход — оплаченные в этом году акты, включая архивных
клиентов; тесты владельца, отозванные, неоплаченные и прошлогодние — нет.
О пройденном пороге владелец узнаёт при отметке оплаты, один раз за порог.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from core_api import npd_limit
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ClientNotice, Lead, LeadSource, Scope, WorkAct, WorkActStatus
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_client_archive import _agreement, _cleanup, _key, _seed


@pytest.mark.parametrize(
    ("pct", "expected"), [(0, "ok"), (79, "ok"), (80, "warn"), (94, "warn"), (95, "alert"), (100, "over"), (130, "over")]
)
def test_level(pct, expected) -> None:
    assert npd_limit.level(pct) == expected


def _tg() -> int:
    return 9_700_000_000 + int(uuid4().hex[:5], 16)


def _act(agreement_id, lead_id, amount: int, status=WorkActStatus.paid, **extra) -> WorkAct:
    values = dict(
        act_number=f"AC-NPD-{uuid4().hex[:8].upper()}",
        agreement_id=agreement_id,
        lead_id=lead_id,
        description_text="Консультация",
        amount_minor=amount,
        status=status,
        sent_at=datetime.now(timezone.utc),
    )
    values.update(extra)
    return WorkAct(**values)


@pytest.fixture(autouse=True)
def clean_notices():
    yield
    get_settings.cache_clear()
    db = SessionLocal()
    try:
        db.execute(delete(ClientNotice).where(ClientNotice.event_key.like("npd_limit:%")))
        db.commit()
    finally:
        db.close()


def _income() -> int:
    db = SessionLocal()
    try:
        return npd_limit.summary(db, datetime.now(timezone.utc))["income_minor"]
    finally:
        db.close()


def test_income_counts_this_year_paid_acts_including_archive(monkeypatch) -> None:
    staff_tg = _tg()
    monkeypatch.setenv("TEST_TELEGRAM_IDS", str(staff_tg))
    get_settings.cache_clear()
    before = _income()

    real = _seed(_tg())
    now = datetime.now(timezone.utc)
    last_year = npd_limit.year_start(now) - timedelta(days=1)
    db = SessionLocal()
    try:
        # Реальный клиент, уже убранный в архив: его деньги — всё равно доход.
        db.get(Lead, real["lead_id"]).archived_at = now
        agreement_id = real["agreement_id"]
        lead_id = real["lead_id"]
        db.add_all(
            [
                _act(agreement_id, lead_id, 1_000_000, paid_at=now),
                _act(agreement_id, lead_id, 2_000_000, paid_at=last_year),
                _act(agreement_id, lead_id, 3_000_000, status=WorkActStatus.sent),
                _act(agreement_id, lead_id, 4_000_000, paid_at=now, cancelled_at=now),
            ]
        )
        staff = Lead(name="Владелец", contact="@me", telegram_user_id=staff_tg, source=LeadSource.telegram_bot)
        db.add(staff)
        db.flush()
        staff_agreement = _agreement(staff.id, None)
        db.add(staff_agreement)
        db.flush()
        db.add(_act(staff_agreement.id, staff.id, 5_000_000, paid_at=now))
        db.commit()
        staff_id = str(staff.id)
    finally:
        db.close()
    try:
        assert _income() - before == 1_000_000
    finally:
        _cleanup([], [real["lead_id"], staff_id])


def test_owner_hears_about_each_threshold_once(monkeypatch) -> None:
    seeded = _seed(_tg())
    name = f"pytest.npd.{uuid4().hex}"
    headers = {"X-API-Key": _key(Scope.admin, name)}
    client = TestClient(app)
    big = 10**12  # огромная сумма: чужие оплаты в тестовой базе на проценты не влияют

    def sent(amount: int) -> str:
        db = SessionLocal()
        try:
            act = _act(seeded["agreement_id"], seeded["lead_id"], amount, status=WorkActStatus.sent)
            db.add(act)
            db.commit()
            return str(act.id)
        finally:
            db.close()

    def notices() -> list[str]:
        db = SessionLocal()
        try:
            return sorted(db.scalars(select(ClientNotice.event_key).where(ClientNotice.event_key.like("npd_limit:%"))))
        finally:
            db.close()

    try:
        limit = (_income() + big) * 100 // 85
        monkeypatch.setenv("NPD_ANNUAL_LIMIT_MINOR", str(limit))
        get_settings.cache_clear()
        year = datetime.now(timezone.utc).astimezone(npd_limit._TZ).year

        assert client.patch(f"/api/v1/work-acts/{sent(big)}/paid", json={}, headers=headers).status_code == 200
        assert notices() == [f"npd_limit:{year}:80"]

        # Ещё одна оплата в той же зоне — второго сообщения нет.
        assert client.patch(f"/api/v1/work-acts/{sent(100)}/paid", json={}, headers=headers).status_code == 200
        assert notices() == [f"npd_limit:{year}:80"]

        # Перешли 95% — новое, одно.
        push = limit * 96 // 100 - _income()
        assert client.patch(f"/api/v1/work-acts/{sent(push)}/paid", json={}, headers=headers).status_code == 200
        assert notices() == [f"npd_limit:{year}:80", f"npd_limit:{year}:95"]

        db = SessionLocal()
        try:
            text = db.scalar(select(ClientNotice.text).where(ClientNotice.event_key == f"npd_limit:{year}:95"))
        finally:
            db.close()
        assert "До лимита осталось" in text

        finance = client.get("/api/v1/lawyer/finance", headers=headers).json()["npd"]
        assert finance["level"] == "alert"
        assert finance["limit_minor"] == limit
    finally:
        _cleanup([name], [seeded["lead_id"]])
