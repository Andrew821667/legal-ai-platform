"""Сроки практики для календаря телефона (подписка ICS на сайте).

Сроки жили только в рабочем месте: чтобы о них вспомнить, его нужно было
открыть. Календарь телефона напоминает сам. Здесь — список событий, сайт
превращает его в ICS.

Имён клиентов в событиях нет: календарь синхронизируется с облаком
(iCloud, Google), и имя клиента рядом с делом там — передача персональных
данных третьему лицу за рубеж. Событие несёт номер дела или документа и
ссылку на карточку — всё остальное юрист видит, открыв её.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.config import get_settings
from core_api.lead_notifications import _LEGAL_AREA_LABELS
from core_api.models import (
    Lead,
    LegalIntake,
    LegalIntakeStatus,
    Practice,
    ServiceAgreement,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)
from core_api.staff import real_client

MOSCOW = ZoneInfo("Europe/Moscow")
# Прошедшие сроки держим месяц — чтобы пропущенное было видно, — будущие год.
PAST = timedelta(days=30)
AHEAD = timedelta(days=365)


def _day(value: datetime) -> str:
    return value.astimezone(MOSCOW).date().isoformat()


def _short(value) -> str:
    return str(value).split("-", 1)[0].upper()


def _matter(intake: LegalIntake) -> str:
    if intake.practice == Practice.legal and intake.legal_area is not None:
        return _LEGAL_AREA_LABELS.get(intake.legal_area.value, "Юридическое дело")
    return {Practice.engineering: "Разработка", Practice.hybrid: "Автоматизация"}.get(intake.practice, "Дело")


def events(db: Session, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    since, until = now - PAST, now + AHEAD
    found: list[dict] = []

    intakes = db.execute(
        select(LegalIntake)
        .join(Lead, Lead.id == LegalIntake.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(real_client(Lead.telegram_user_id))
        .where(LegalIntake.deadline_at.is_not(None))
        .where(LegalIntake.deadline_at.between(since, until))
        .where(LegalIntake.status.not_in([LegalIntakeStatus.closed, LegalIntakeStatus.declined]))
    ).scalars()
    for intake in intakes:
        found.append({
            "uid": f"intake-{intake.id}",
            "kind": "intake_deadline",
            "date": _day(intake.deadline_at),
            "title": f"Срок по делу: {_matter(intake)} · №{_short(intake.id)}",
            "lead_id": str(intake.lead_id),
        })

    agreements = db.execute(
        select(ServiceAgreement)
        .join(Lead, Lead.id == ServiceAgreement.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(real_client(Lead.telegram_user_id))
        .where(ServiceAgreement.status.in_([ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed]))
        .where(ServiceAgreement.expires_at.is_not(None))
        .where(ServiceAgreement.expires_at.between(since, until))
    ).scalars()
    for agreement in agreements:
        kind = "допсоглашение" if agreement.parent_agreement_id else "договор"
        found.append({
            "uid": f"agreement-{agreement.id}",
            "kind": "agreement_expires",
            "date": _day(agreement.expires_at),
            "title": f"Истекает {kind} {agreement.agreement_number} — клиент не подписал",
            "lead_id": str(agreement.lead_id) if agreement.lead_id else None,
        })

    # Срок оплаты акта — тот же, что у «Просрочено» в рабочем месте.
    days = max(get_settings().act_payment_days, 1)
    acts = db.execute(
        select(WorkAct)
        .join(Lead, Lead.id == WorkAct.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(real_client(Lead.telegram_user_id))
        .where(WorkAct.cancelled_at.is_(None))
        .where(WorkAct.status == WorkActStatus.sent)
        .where(WorkAct.sent_at.is_not(None))
        .where(WorkAct.sent_at.between(since - timedelta(days=days), until))
    ).scalars()
    for act in acts:
        found.append({
            "uid": f"act-{act.id}",
            "kind": "act_payment_due",
            "date": _day(act.sent_at + timedelta(days=days)),
            "title": f"Срок оплаты: акт {act.act_number}",
            "lead_id": str(act.lead_id) if act.lead_id else None,
        })

    found.sort(key=lambda event: (event["date"], event["uid"]))
    return found
