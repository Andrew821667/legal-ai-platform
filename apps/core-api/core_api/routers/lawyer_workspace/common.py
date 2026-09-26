"""Общее для экранов рабочего места: сроки, подписи, связи обращений."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.models import (
    AgreementTemplate,
    IntakeLink,
    IntakeLinkType,
    Lead,
    LegalIntake,
    LegalIntakeStatus,
    ServiceAgreementStatus,
)

# Сколько дней ждать реакции клиента, прежде чем напомнить о себе юристу.
_AWAITING_CLIENT_DAYS = 3

# За сколько дней предупреждать, что предложение вот-вот сгорит.
_EXPIRING_SOON_DAYS = 3

# За сколько дней напоминать о сроке, который юрист проставил по обращению.
_DEADLINE_SOON_DAYS = 3

# Статусы, из которых договор ещё может сдвинуться.
_OPEN_AGREEMENT_STATUSES = (
    ServiceAgreementStatus.draft,
    ServiceAgreementStatus.sent,
    ServiceAgreementStatus.viewed,
)


def _lead_title(lead: Lead | None) -> str:
    if lead is None:
        return "без имени"
    return lead.name or lead.contact or "без имени"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _days_since(value: datetime | None) -> int | None:
    if value is None:
        return None
    delta = datetime.now(timezone.utc) - value.astimezone(timezone.utc)
    return max(0, delta.days)


def _days_until(value: datetime | None) -> int | None:
    """Сколько целых дней осталось. Отрицательное — срок уже прошёл."""
    if value is None:
        return None
    # timedelta.days округляет вниз: 2,5 дня впереди — это 2 полных дня, а
    # полдня назад — уже -1, то есть «просрочено».
    return (value.astimezone(timezone.utc) - datetime.now(timezone.utc)).days


_LIVE_INTAKE_EXCLUDED = (LegalIntakeStatus.closed, LegalIntakeStatus.declined)


def _worked_without_agreement(intakes: list[tuple[bool, LegalIntakeStatus]]) -> bool:
    """Клиента ведут без договора и условий от юриста никто не ждёт.

    Хотя бы одно обращение отмечено «без договора», и нет живого обращения,
    по которому решение ещё не принято: у постоянного клиента с новым
    вопросом этап должен звать готовить условия, а не прятать его.
    """
    worked = any(flag for flag, _ in intakes)
    awaiting_terms = any(not flag and status not in _LIVE_INTAKE_EXCLUDED for flag, status in intakes)
    return worked and not awaiting_terms


def _package_for(db: Session, item: LegalIntake) -> dict | None:
    """Пакет, выбранный клиентом на сайте, и заготовка юриста под него."""
    if not item.package_id:
        return None
    template_id = db.scalar(select(AgreementTemplate.id).where(AgreementTemplate.package_id == item.package_id))
    return {
        "id": item.package_id,
        "title": item.package_title,
        "price_text": item.package_price_text,
        "template_id": str(template_id) if template_id else None,
    }


def _intake_links_for(db: Session, intake_id: uuid.UUID) -> list[dict]:
    """Обращения других клиентов, связанные с этим по одному фактическому делу.

    Связь хранится направленной (intake_id → linked_intake_id), но видна с
    любого конца — юрист открывает и то, и другое обращение, и не обязан
    помнить, кто на какой стороне строки. "role" уже посчитана относительно
    intake_id, который передан сюда: у второстепенного обращения — свой
    role, у основного — свой.
    """
    rows = db.execute(
        select(IntakeLink).where(
            or_(IntakeLink.intake_id == intake_id, IntakeLink.linked_intake_id == intake_id)
        )
    ).scalars().all()
    if not rows:
        return []

    partner_intake_ids = {
        (row.linked_intake_id if row.intake_id == intake_id else row.intake_id) for row in rows
    }
    partner_intakes = {
        item.id: item
        for item in db.scalars(select(LegalIntake).where(LegalIntake.id.in_(partner_intake_ids)))
    }
    partner_lead_ids = {item.lead_id for item in partner_intakes.values()}
    leads_by_id = {
        lead.id: lead
        for lead in db.scalars(select(Lead).where(Lead.id.in_(partner_lead_ids)))
    } if partner_lead_ids else {}

    result: list[dict] = []
    for row in rows:
        partner_intake_id = row.linked_intake_id if row.intake_id == intake_id else row.intake_id
        partner = partner_intakes.get(partner_intake_id)
        if partner is None:
            continue
        if row.link_type == IntakeLinkType.joint:
            role = "joint"
        else:
            role = "subordinate" if row.intake_id == intake_id else "main"
        result.append(
            {
                "link_id": str(row.id),
                "role": role,
                "note": row.note,
                "linked_lead_id": str(partner.lead_id),
                "linked_client": _lead_title(leads_by_id.get(partner.lead_id)),
                # Какое именно дело того клиента: после того как у клиента
                # может быть несколько обращений, одного имени мало.
                "linked_intake_id": str(partner.id),
                "linked_practice": partner.practice.value,
                "linked_legal_area": partner.legal_area.value,
                "linked_category": partner.category,
                "linked_intake_created_at": _iso(partner.created_at),
                "created_at": _iso(row.created_at),
            }
        )
    return result
