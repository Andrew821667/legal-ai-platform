"""Сводка за неделю владельцу.

Закрепляется: приходит с понедельника 09:00 по Москве, один раз за неделю;
считает прошлую неделю — новых клиентов по источникам, договоры, оплаты —
без тестовых аккаунтов; напоминает, что ждёт владельца сейчас.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from core_api import weekly_digest
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.models import (
    ClientNotice,
    ConsultationSlot,
    Lead,
    LeadSource,
    LegalIntake,
    LegalIntakeStatus,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)
from sqlalchemy import delete, select

from test_client_archive import _agreement, _cleanup

MSK = timezone(timedelta(hours=3))


@pytest.fixture(autouse=True)
def clean_notices():
    def clean():
        db = SessionLocal()
        try:
            db.execute(delete(ClientNotice).where(ClientNotice.event_key.like("weekly_digest:%")))
            db.commit()
        finally:
            db.close()

    clean()
    yield
    get_settings.cache_clear()
    clean()


def test_schedule() -> None:
    monday = datetime(2026, 9, 21, tzinfo=MSK)
    assert not weekly_digest.is_due(monday.replace(hour=8, minute=59))
    assert weekly_digest.is_due(monday.replace(hour=9))
    assert weekly_digest.is_due(monday + timedelta(days=1, hours=3))
    wednesday = monday + timedelta(days=2, hours=15)
    assert weekly_digest.week_start(wednesday) == monday.astimezone(timezone.utc)
    assert weekly_digest.week_key(wednesday) == "weekly_digest:2026-W39"


def test_digest_counts_last_week_without_tests(monkeypatch) -> None:
    staff_tg = 9_800_000_000 + int(uuid4().hex[:5], 16)
    monkeypatch.setenv("TEST_TELEGRAM_IDS", str(staff_tg))
    get_settings.cache_clear()
    now = weekly_digest.week_start(datetime.now(timezone.utc)) + timedelta(days=2, hours=12)
    last_week = weekly_digest.week_start(now) - timedelta(days=5)
    created: list[str] = []
    db = SessionLocal()
    try:
        client = Lead(
            name="Сводка", contact="@digest", telegram_user_id=staff_tg + 1,
            source=LeadSource.telegram_bot, cta_variant="reader_referral", created_at=last_week,
        )
        owner = Lead(
            name="Владелец", contact="@me", telegram_user_id=staff_tg,
            source=LeadSource.telegram_bot, created_at=last_week,
        )
        db.add_all([client, owner])
        db.flush()
        created += [str(client.id), str(owner.id)]
        intake = LegalIntake(
            lead_id=client.id, description="Обращение для сводки.", status=LegalIntakeStatus.accepted,
            created_at=last_week,
        )
        db.add(intake)
        db.flush()
        agreement = _agreement(
            client.id, intake.id, amount_minor=12_345_600, sent_at=last_week, signed_at=last_week,
            status=ServiceAgreementStatus.signed,
        )
        db.add(agreement)
        db.flush()
        db.add(
            WorkAct(
                act_number=f"AC-DG-{uuid4().hex[:6].upper()}", agreement_id=agreement.id, lead_id=client.id,
                description_text="Работа", amount_minor=5_000_000, status=WorkActStatus.paid,
                sent_at=last_week, paid_at=last_week,
            )
        )
        # Тест владельца на той же неделе — в сводку не попадает.
        owner_agreement = _agreement(owner.id, None, amount_minor=99_900_000, sent_at=last_week, signed_at=last_week)
        db.add(owner_agreement)
        db.commit()

        text = weekly_digest.build(db, now)
    finally:
        db.close()
    try:
        assert "Новых клиентов: 1 (канал — 1)" in text
        assert "Обращений: 1" in text
        assert "Договоров отправлено: 1, подписано: 1 на 123 456 ₽" in text
        assert "Оплачено: 1 акт на 50 000 ₽" in text
        assert "999 000" not in text
        assert "/lawyer" in text
    finally:
        _cleanup([], created)


def test_queued_once_a_week(monkeypatch) -> None:
    monday_morning = datetime(2026, 9, 21, 9, 30, tzinfo=MSK)
    assert weekly_digest.maybe_queue(monday_morning.replace(hour=8)) == {"skipped": "not_yet"}
    assert weekly_digest.maybe_queue(monday_morning) == {"queued": "weekly_digest:2026-W39"}
    assert weekly_digest.maybe_queue(monday_morning + timedelta(hours=5)) == {"skipped": "sent"}
    db = SessionLocal()
    try:
        texts = list(db.scalars(select(ClientNotice.text).where(ClientNotice.event_key.like("weekly_digest:%"))))
    finally:
        db.close()
    assert len(texts) == 1 and texts[0].startswith("Неделя 14.09–20.09")

    monkeypatch.setenv("WEEKLY_DIGEST_ENABLED", "false")
    get_settings.cache_clear()
    assert weekly_digest.maybe_queue(monday_morning + timedelta(days=7)) == {"skipped": "disabled"}


def test_digest_shows_money_by_source_upsell_and_ab() -> None:
    # Отдельная неделя в будущем — чтобы суммы не смешивались с данными других тестов.
    now = datetime(2031, 1, 15, 12, tzinfo=MSK)
    last_week = weekly_digest.week_start(now) - timedelta(days=5)
    created: list[str] = []
    slot_id = None
    db = SessionLocal()
    try:
        tg = 9_700_000_000 + int(uuid4().hex[:5], 16)
        site = Lead(name="С сайта", contact="+79990000000", source=LeadSource.website_form, created_at=last_week)
        bot_a = Lead(
            name="Вариант A", contact="@a", telegram_user_id=tg, source=LeadSource.telegram_bot,
            cta_variant="A", created_at=last_week,
        )
        bot_b = Lead(
            name="Вариант B", contact="@b", telegram_user_id=tg + 1, source=LeadSource.telegram_bot,
            cta_variant="B", created_at=last_week,
        )
        db.add_all([site, bot_a, bot_b])
        db.flush()
        created += [str(site.id), str(bot_a.id), str(bot_b.id)]
        db.add(LegalIntake(lead_id=bot_a.id, description="Обращение варианта A.", status=LegalIntakeStatus.accepted))
        main = _agreement(site.id, None, amount_minor=10_000_000)
        db.add(main)
        db.flush()
        # Допсоглашение к действующему договору — допродажа недели.
        db.add(_agreement(site.id, None, parent_agreement_id=main.id, amount_minor=2_000_000, signed_at=last_week))
        db.add(
            WorkAct(
                act_number=f"AC-RV-{uuid4().hex[:6].upper()}", agreement_id=main.id, lead_id=site.id,
                description_text="Работа", amount_minor=5_000_000, status=WorkActStatus.paid,
                sent_at=last_week, paid_at=last_week,
            )
        )
        slot = ConsultationSlot(
            starts_at=last_week, status="confirmed", lead_id=bot_a.id, price_minor=490_000, confirmed_at=last_week,
        )
        db.add(slot)
        db.commit()
        slot_id = slot.id

        text = weekly_digest.build(db, now)
    finally:
        if slot_id is not None:
            db.execute(delete(ConsultationSlot).where(ConsultationSlot.id == slot_id))
            db.commit()
        db.close()
    try:
        assert "Выручка: 54 900 ₽ (форма на сайте — 50 000 ₽, бот напрямую — 4 900 ₽)" in text
        assert "Консультаций оплачено: 1 на 4 900 ₽" in text
        assert "Допсоглашений подписано: 1 на 20 000 ₽" in text
        assert "Призыв в боте (A/B): A — 1 → обращений 1; B — 1 → обращений 0" in text
    finally:
        _cleanup([], created)
