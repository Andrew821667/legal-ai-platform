"""Воронка практики: пришёл → обращение → договор → подписал → оплатил.

Закрепляется: считается когорта пришедших за период, по источникам; тестовые
аккаунты, архив и пришедшие раньше периода не считаются; допсоглашение и
отозванный акт не двигают клиента по воронке.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from core_api import practice_funnel
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
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

from test_client_archive import _agreement, _cleanup, _key


@pytest.mark.parametrize(
    ("source", "cta", "notes", "expected"),
    [
        (LeadSource.telegram_bot, "reader_referral", None, "channel"),
        (LeadSource.telegram_bot, None, "[READER_REFERRAL] post_id=1", "channel"),
        (LeadSource.telegram_bot, "channel_post", None, "channel"),
        (LeadSource.telegram_bot, None, "[CHANNEL_POST]\npost_id=1", "channel"),
        (LeadSource.telegram_channel, None, None, "channel"),
        (LeadSource.telegram_bot, "legal_help", None, "site_bot"),
        (LeadSource.website_form, "legal_help", None, "site_form"),
        (LeadSource.miniapp_form, None, None, "miniapp_form"),
        (LeadSource.telegram_bot, "A", None, "bot"),
        (None, None, None, "bot"),
    ],
)
def test_source_key(source, cta, notes, expected) -> None:
    assert practice_funnel.source_key(source, cta, notes) == expected


def _tg() -> int:
    return 9_600_000_000 + int(uuid4().hex[:5], 16)


@pytest.fixture()
def staff_id(monkeypatch: pytest.MonkeyPatch):
    telegram_id = _tg()
    monkeypatch.setenv("TEST_TELEGRAM_IDS", str(telegram_id))
    get_settings.cache_clear()
    yield telegram_id
    get_settings.cache_clear()


def test_cohort_by_source_without_tests_archive_and_old_leads(staff_id) -> None:
    since = datetime.now(timezone.utc) - timedelta(seconds=1)
    created: list[str] = []
    db = SessionLocal()
    try:
        def lead(**kwargs) -> Lead:
            values = dict(name="Воронка", contact="@test", telegram_user_id=_tg(), source=LeadSource.telegram_bot)
            values.update(kwargs)
            row = Lead(**values)
            db.add(row)
            db.flush()
            created.append(str(row.id))
            return row

        def intake(row: Lead) -> LegalIntake:
            item = LegalIntake(lead_id=row.id, description="Обращение для проверки воронки.", status=LegalIntakeStatus.accepted)
            db.add(item)
            db.flush()
            return item

        # Из канала — дошёл до оплаты; допсоглашение и отозванный акт не в счёт.
        paying = lead(cta_variant="reader_referral")
        paying_intake = intake(paying)
        main = _agreement(paying.id, paying_intake.id, sent_at=since + timedelta(milliseconds=500))
        db.add(main)
        db.flush()
        db.add(
            _agreement(
                paying.id,
                paying_intake.id,
                agreement_number=f"{main.agreement_number}-DS1",
                parent_agreement_id=main.id,
            )
        )
        for amount, status, cancelled in ((5_000_000, WorkActStatus.paid, None), (7_000_000, WorkActStatus.paid, since)):
            db.add(
                WorkAct(
                    act_number=f"AC-FN-{uuid4().hex[:6].upper()}",
                    agreement_id=main.id,
                    lead_id=paying.id,
                    description_text="Работа выполнена.",
                    amount_minor=amount,
                    status=status,
                    cancelled_at=cancelled,
                )
            )

        # Из бота — только обращение; договор ему составлен, но не отправлен.
        asking = lead(cta_variant="A")
        asking_intake = intake(asking)
        db.add(_agreement(asking.id, asking_intake.id, status=ServiceAgreementStatus.draft, signed_at=None))

        # С сайта — только пришёл.
        lead(source=LeadSource.website_form, telegram_user_id=None)

        # Не считаются: архив, тестовый аккаунт владельца, пришедший до периода.
        lead(archived_at=since)
        lead(telegram_user_id=staff_id)
        lead(created_at=since - timedelta(days=400))
        db.commit()

        result = practice_funnel.build(db, since=since, now=datetime.now(timezone.utc) + timedelta(seconds=1))
    finally:
        db.close()

    try:
        stages = {s["key"]: s["count"] for s in result["stages"]}
        assert stages == {"leads": 3, "intake": 2, "agreement": 1, "signed": 1, "paid": 1}
        by_step = {s["key"]: s["from_previous_pct"] for s in result["stages"]}
        assert by_step["leads"] is None
        assert by_step["intake"] == 67
        assert result["paid_minor"] == 5_000_000

        sources = {s["key"]: s for s in result["sources"]}
        assert list(sources) == ["channel", "site_form", "bot"]
        assert sources["channel"]["counts"] == {"leads": 1, "intake": 1, "agreement": 1, "signed": 1, "paid": 1}
        assert sources["channel"]["paid_minor"] == 5_000_000
        assert sources["bot"]["counts"]["intake"] == 1
        assert sources["bot"]["counts"]["agreement"] == 0
        assert sources["site_form"]["counts"]["leads"] == 1
    finally:
        _cleanup([], created)


def test_endpoint_and_period_bounds() -> None:
    name = f"pytest.funnel.{uuid4().hex}"
    key = _key(Scope.admin, name)
    client = TestClient(app)
    try:
        response = client.get("/api/v1/lawyer/funnel?days=30", headers={"X-API-Key": key})
        assert response.status_code == 200
        body = response.json()
        assert body["days"] == 30
        assert [s["key"] for s in body["stages"]] == ["leads", "intake", "agreement", "signed", "paid"]
        assert client.get("/api/v1/lawyer/funnel?days=1", headers={"X-API-Key": key}).status_code == 422
        assert client.get("/api/v1/lawyer/funnel").status_code == 401
    finally:
        _cleanup([name], [])
