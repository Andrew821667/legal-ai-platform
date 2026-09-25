"""Рабочее место юриста: что требует внимания и карточка клиента.

Собирает данные, разбросанные по обращениям, диалогам, соглашениям и
документам, в два ответа. Дробить на десяток запросов нельзя: экран
открывается в мессенджере, часто с телефона и не всегда на быстрой сети, и
десять последовательных обращений превращаются в секунды ожидания.

Главный экран отвечает на один вопрос: что стоит без движения из-за меня.
Список всех клиентов такого ответа не даёт — по нему приходится вспоминать,
кому что обещал. Поэтому «Сегодня» показывает не всё подряд, а застрявшее:
неотправленный черновик договора, вопрос клиента без ответа, обращение, по
которому никто не связался.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api import case_stage, practice_funnel, telegram_delivery
from core_api.config import get_settings
from core_api.db import get_db
from core_api.staff import is_staff, real_client, staff_telegram_ids
from core_api.models import (
    ActorType,
    AuditLog,
    ContractJob,
    Event,
    IntakeClarification,
    IntakeDocument,
    IntakeLink,
    IntakeLinkType,
    Lead,
    LegalIntake,
    LegalIntakeStatus,
    NdaPersonalDataConsent,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
    ServiceAgreementStatus,
    SpecialConsultationOrder,
    SpecialConsultationPayment,
    TelegramDelivery,
    WorkAct,
    WorkActStatus,
)

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])

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


@router.get("/today")
def today(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Что стоит без движения и ждёт юриста.

    Каждый раздел — отдельная причина, по которой дело не двигается. Пустой
    раздел не показывается: экран должен читаться как список задач, а не как
    отчёт о том, чего нет.
    """
    _ = identity
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(days=_AWAITING_CLIENT_DAYS)

    # 1. Договор составлен, но не ушёл клиенту. Самая обидная задержка: работа
    #    сделана, а клиент ждёт и не знает почему.
    drafts = db.execute(
        select(ServiceAgreement, Lead)
        .outerjoin(Lead, Lead.id == ServiceAgreement.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(ServiceAgreement.status == ServiceAgreementStatus.draft)
        .order_by(ServiceAgreement.created_at)
    ).all()

    # 2. Клиент спросил по договору, ответа нет. Считаем по последнему
    #    сообщению: если оно от клиента — очередь наша.
    last_message = (
        select(
            ServiceAgreementMessage.agreement_id.label("agreement_id"),
            func.max(ServiceAgreementMessage.created_at).label("last_at"),
        )
        .group_by(ServiceAgreementMessage.agreement_id)
        .subquery()
    )
    unanswered = db.execute(
        select(ServiceAgreementMessage, ServiceAgreement, Lead)
        .join(
            last_message,
            (last_message.c.agreement_id == ServiceAgreementMessage.agreement_id)
            & (last_message.c.last_at == ServiceAgreementMessage.created_at),
        )
        .join(ServiceAgreement, ServiceAgreement.id == ServiceAgreementMessage.agreement_id)
        .outerjoin(Lead, Lead.id == ServiceAgreement.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(ServiceAgreementMessage.role == ServiceAgreementMessageRole.client)
        .order_by(ServiceAgreementMessage.created_at)
    ).all()

    # 3. До клиента не дозвонились: заявка пришла не из Telegram либо бот
    #    заблокирован. Написать первым он не может — нужен человек.
    unreachable = db.execute(
        select(LegalIntake, Lead)
        .join(Lead, Lead.id == LegalIntake.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(LegalIntake.outreach_blocked_reason.is_not(None))
        .where(LegalIntake.status.not_in([LegalIntakeStatus.closed, LegalIntakeStatus.declined]))
        .order_by(LegalIntake.created_at)
    ).all()

    # 4. Договор отправлен, но клиент молчит несколько дней.
    awaiting = db.execute(
        select(ServiceAgreement, Lead)
        .outerjoin(Lead, Lead.id == ServiceAgreement.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(
            ServiceAgreement.status.in_(
                [ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed]
            )
        )
        .where(ServiceAgreement.sent_at.is_not(None))
        .where(ServiceAgreement.sent_at < stale_before)
        # Сгорающее предложение показываем отдельным разделом: там другое
        # действие — не напомнить, а успеть переиздать. Дважды в списке дел
        # одно и то же дело выглядит как две задачи.
        .where(
            or_(
                ServiceAgreement.expires_at.is_(None),
                ServiceAgreement.expires_at >= now + timedelta(days=_EXPIRING_SOON_DAYS),
            )
        )
        .order_by(ServiceAgreement.sent_at)
    ).all()

    # 4а. Бот передал клиента юристу, а обращения нет. Разговор шёл в
    #     консультанте бота и до анкеты не дошёл — такой клиент не попадал ни
    #     в один раздел задач, и из четырёх таких на проде юрист не узнал ни
    #     об одном. Договора тоже нет — иначе он уже в других разделах.
    has_intake = select(LegalIntake.lead_id).where(LegalIntake.lead_id.is_not(None))
    has_agreement = select(ServiceAgreement.lead_id).where(ServiceAgreement.lead_id.is_not(None))
    handed_off = db.execute(
        select(Lead)
        .where(Lead.archived_at.is_(None))
        .where(Lead.conversation_stage == "handoff")
        .where(Lead.id.not_in(has_intake))
        .where(Lead.id.not_in(has_agreement))
        .order_by(Lead.created_at)
    ).scalars().all()

    # 5. Обращение без договора: диалог прошёл, а условия не предложены.
    with_agreement = select(ServiceAgreement.intake_id).where(
        ServiceAgreement.intake_id.is_not(None)
    )
    no_agreement = db.execute(
        select(LegalIntake, Lead)
        .join(Lead, Lead.id == LegalIntake.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(LegalIntake.id.not_in(with_agreement))
        # Юрист уже решил: договор не нужен. Напоминать о нём — шум.
        .where(LegalIntake.without_agreement.is_(False))
        .where(
            LegalIntake.status.not_in(
                [LegalIntakeStatus.closed, LegalIntakeStatus.declined]
            )
        )
        .order_by(LegalIntake.created_at)
    ).all()

    # 6. Предложение вот-вот сгорит. В «истёк» договор переводится только
    #    когда клиент сам откроет просроченное предложение (service_agreements.py):
    #    до тех пор о сгорающем сроке юристу узнать неоткуда, а после — поздно,
    #    редакцию придётся составлять заново.
    expiring = db.execute(
        select(ServiceAgreement, Lead)
        .outerjoin(Lead, Lead.id == ServiceAgreement.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(
            ServiceAgreement.status.in_(
                [ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed]
            )
        )
        .where(ServiceAgreement.expires_at.is_not(None))
        .where(ServiceAgreement.expires_at < now + timedelta(days=_EXPIRING_SOON_DAYS))
        .order_by(ServiceAgreement.expires_at)
    ).all()

    # 7. Срок по обращению. В отличие от остальных разделов этот наполняет сам
    #    юрист: колонка `deadline` — слова клиента («к этому четвергу»), и
    #    напоминать по ним нельзя, а `deadline_at` он проставил осознанно.
    deadline_soon = db.execute(
        select(LegalIntake, Lead)
        .join(Lead, Lead.id == LegalIntake.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(LegalIntake.deadline_at.is_not(None))
        .where(LegalIntake.deadline_at < now + timedelta(days=_DEADLINE_SOON_DAYS))
        .where(LegalIntake.status.not_in([LegalIntakeStatus.closed, LegalIntakeStatus.declined]))
        .order_by(LegalIntake.deadline_at)
    ).all()

    # 8. Деньги по актам: клиент сказал «оплатил» — сверить поступление;
    #    срок оплаты вышел — напомнить. Раньше акт после отправки пропадал
    #    из виду, пока юрист сам не откроет карточку.
    open_acts = db.execute(
        _counted_acts().where(WorkAct.status.in_(_ACT_OPEN)).order_by(WorkAct.sent_at)
    ).all()
    acts_claimed = [(a, lead) for a, lead in open_acts if a.status == WorkActStatus.claimed_paid]
    acts_overdue = [(a, lead) for a, lead in open_acts if _overdue(a, now)]

    # 9. Не ушло в Telegram: не ушло совсем или повтор затянулся. Раньше такие
    #    сбои оседали в логе, и о них никто не знал.
    undelivered = db.execute(
        select(TelegramDelivery, Lead)
        .outerjoin(Lead, Lead.id == TelegramDelivery.lead_id)
        .where(TelegramDelivery.dismissed_at.is_(None))
        .where(
            or_(
                TelegramDelivery.status == "failed",
                and_(
                    TelegramDelivery.status == "pending",
                    TelegramDelivery.created_at < now - telegram_delivery.STUCK_AFTER,
                ),
            )
        )
        .order_by(TelegramDelivery.created_at.desc())
        .limit(50)
    ).all()

    return {
        "generated_at": _iso(now),
        "sections": [
            {
                "key": "draft_not_sent",
                "title": "Договор составлен, но не отправлен",
                "hint": "Работа сделана, клиент ждёт и не знает почему.",
                "items": [
                    {
                        "agreement_id": str(a.id),
                        "lead_id": str(a.lead_id) if a.lead_id else None,
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "subject": a.subject[:160],
                        "price_text": a.price_text,
                        "created_at": _iso(a.created_at),
                        "days_waiting": _days_since(a.created_at),
                    }
                    for a, lead in drafts
                ],
            },
            {
                "key": "client_question",
                "title": "Вопрос клиента без ответа",
                "hint": "Последнее слово в переписке за клиентом.",
                "items": [
                    {
                        "agreement_id": str(a.id),
                        "lead_id": str(a.lead_id) if a.lead_id else None,
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "question": m.text[:300],
                        "asked_at": _iso(m.created_at),
                        "days_waiting": _days_since(m.created_at),
                    }
                    for m, a, lead in unanswered
                ],
            },
            {
                "key": "unreachable",
                "title": "Связаться не удалось",
                "hint": "Бот не может написать первым — нужен звонок или почта.",
                "items": [
                    {
                        "intake_id": str(i.id),
                        "lead_id": str(i.lead_id),
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "contact": lead.contact,
                        "reason": i.outreach_blocked_reason,
                        "created_at": _iso(i.created_at),
                        "days_waiting": _days_since(i.created_at),
                    }
                    for i, lead in unreachable
                ],
            },
            {
                "key": "bot_handoff",
                "title": "Бот передал вам клиента",
                "hint": "Разговор с ботом дошёл до передачи юристу, а обращения нет. Напишите клиенту или уберите в архив.",
                "items": [
                    {
                        "lead_id": str(lead.id),
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id),
                        "contact": lead.contact,
                        "need": (lead.pain_point or lead.specific_need or "")[:160] or None,
                        "created_at": _iso(lead.created_at),
                        "days_waiting": _days_since(lead.last_message_at or lead.created_at),
                    }
                    for lead in handed_off
                ],
            },
            {
                "key": "awaiting_client",
                "title": f"Клиент молчит больше {_AWAITING_CLIENT_DAYS} дней",
                "hint": "Договор отправлен, реакции нет.",
                "items": [
                    {
                        "agreement_id": str(a.id),
                        "lead_id": str(a.lead_id) if a.lead_id else None,
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "subject": a.subject[:160],
                        "status": a.status.value,
                        "sent_at": _iso(a.sent_at),
                        "days_waiting": _days_since(a.sent_at),
                        "last_reminded_at": _iso(a.last_reminded_at),
                    }
                    for a, lead in awaiting
                ],
            },
            {
                "key": "expiring",
                "title": "Предложение истекает",
                "hint": "После этой даты редакцию придётся составлять заново.",
                "items": [
                    {
                        "agreement_id": str(a.id),
                        "lead_id": str(a.lead_id) if a.lead_id else None,
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "subject": a.subject[:160],
                        "status": a.status.value,
                        "expires_at": _iso(a.expires_at),
                        "days_left": _days_until(a.expires_at),
                    }
                    for a, lead in expiring
                ],
            },
            {
                "key": "deadline_soon",
                "title": "Срок по обращению",
                "hint": "Дату вы поставили сами — она подходит.",
                "items": [
                    {
                        "intake_id": str(i.id),
                        "lead_id": str(i.lead_id),
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "legal_area": i.legal_area.value,
                        "practice": i.practice.value,
                        "category": i.category,
                        "status": i.status.value,
                        "deadline_at": _iso(i.deadline_at),
                        "days_left": _days_until(i.deadline_at),
                    }
                    for i, lead in deadline_soon
                ],
            },
            {
                "key": "no_agreement",
                "title": "Обращение без договора",
                "hint": "Условия ещё не предложены.",
                "items": [
                    {
                        "intake_id": str(i.id),
                        "lead_id": str(i.lead_id),
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "legal_area": i.legal_area.value,
                        "practice": i.practice.value,
                        "category": i.category,
                        "status": i.status.value,
                        "urgency": i.urgency.value,
                        "created_at": _iso(i.created_at),
                        "days_waiting": _days_since(i.created_at),
                    }
                    for i, lead in no_agreement
                ],
            },
            {
                "key": "act_claimed_paid",
                "title": "Клиент сообщил об оплате",
                "hint": "Сверьте поступление и отметьте акт оплаченным в карточке.",
                "items": [
                    {
                        "act_id": str(a.id),
                        "act_number": a.act_number,
                        "lead_id": str(a.lead_id) if a.lead_id else None,
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "amount_minor": a.amount_minor,
                        "claimed_paid_at": _iso(a.claimed_paid_at),
                        "days_waiting": _days_since(a.claimed_paid_at),
                    }
                    for a, lead in acts_claimed
                ],
            },
            {
                "key": "act_overdue",
                "title": f"Акт не оплачен дольше {max(get_settings().act_payment_days, 1)} дней",
                "hint": "Напомнить клиенту можно в «Деньгах» или в карточке.",
                "items": [
                    {
                        "act_id": str(a.id),
                        "act_number": a.act_number,
                        "lead_id": str(a.lead_id) if a.lead_id else None,
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "amount_minor": a.amount_minor,
                        "sent_at": _iso(a.sent_at),
                        "last_reminded_at": _iso(a.last_reminded_at),
                        "days_waiting": _days_since(a.sent_at),
                    }
                    for a, lead in acts_overdue
                ],
            },
            {
                "key": "undelivered",
                "title": "Не доставлено в Telegram",
                "hint": "Уведомления повторяются сами; договор, ответ и акт отправьте из карточки заново.",
                "items": [
                    {
                        "delivery_id": str(d.id),
                        "lead_id": str(d.lead_id) if d.lead_id else None,
                        "client": _lead_title(lead) if lead else "Вам — уведомление",
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "kind": d.kind,
                        "kind_label": telegram_delivery.KIND_LABELS.get(d.kind, d.kind),
                        "text": d.text[:200],
                        "delivery_status": d.status,
                        "retryable": d.retryable,
                        "attempts": d.attempts,
                        "last_error": d.last_error,
                        "created_at": _iso(d.created_at),
                        "days_waiting": _days_since(d.created_at),
                    }
                    for d, lead in undelivered
                ],
            },
        ],
        # Связь ядра с Telegram — для плашки над рабочим местом. None, пока
        # проверки не было ни разу.
        "telegram": telegram_delivery.health_snapshot(db),
    }


@router.get("/clients")
def clients(
    search: str = Query("", max_length=120),
    limit: int = Query(50, ge=1, le=200),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Клиенты с обращениями — новые первыми.

    Показываем только тех, у кого есть обращение: в таблице лидов лежат и те,
    кто просто нажал кнопку в боте, и в рабочем месте юриста они лишние.
    """
    _ = identity
    query = (
        select(
            Lead,
            func.count(LegalIntake.id).label("intakes"),
            func.max(LegalIntake.created_at).label("last_intake_at"),
        )
        .join(LegalIntake, LegalIntake.lead_id == Lead.id)
        .where(Lead.archived_at.is_(None))
        .group_by(Lead.id)
        .order_by(func.max(LegalIntake.created_at).desc())
        .limit(limit)
    )
    term = (search or "").strip()
    if term:
        # PostgreSQL installations with the C locale do not case-fold
        # Cyrillic in ILIKE. Include common user-entered variants explicitly.
        patterns = {f"%{value}%" for value in (term, term.capitalize(), term.upper())}
        query = query.where(
            or_(
                *(column.ilike(pattern) for column in (Lead.name, Lead.contact, Lead.company) for pattern in patterns)
            )
        )

    rows = db.execute(query).all()
    lead_ids = [lead.id for lead, _, _ in rows]

    signed_nda: set[uuid.UUID] = set()
    leads_by_telegram: dict[int, set[uuid.UUID]] = {}
    for lead, _, _ in rows:
        if lead.telegram_user_id is not None:
            leads_by_telegram.setdefault(lead.telegram_user_id, set()).add(lead.id)
    if lead_ids:
        checks = [NdaSignature.lead_id.in_(lead_ids)]
        if leads_by_telegram:
            checks.append(NdaSignature.telegram_user_id.in_(leads_by_telegram))
        for nda_lead_id, telegram_user_id in db.execute(
            select(NdaSignature.lead_id, NdaSignature.telegram_user_id).where(or_(*checks))
        ).all():
            if nda_lead_id in lead_ids:
                signed_nda.add(nda_lead_id)
            if telegram_user_id is not None:
                signed_nda.update(leads_by_telegram.get(telegram_user_id, set()))

    # Клиенты, чей последний вопрос остался без ответа.
    awaiting_me: set[uuid.UUID] = set()
    if lead_ids:
        newest = (
            select(
                ServiceAgreementMessage.agreement_id.label("agreement_id"),
                func.max(ServiceAgreementMessage.created_at).label("last_at"),
            )
            .group_by(ServiceAgreementMessage.agreement_id)
            .subquery()
        )
        awaiting_me = {
            lead_id
            for (lead_id,) in db.execute(
                select(ServiceAgreement.lead_id)
                .join(ServiceAgreementMessage, ServiceAgreementMessage.agreement_id == ServiceAgreement.id)
                .join(
                    newest,
                    (newest.c.agreement_id == ServiceAgreementMessage.agreement_id)
                    & (newest.c.last_at == ServiceAgreementMessage.created_at),
                )
                .where(ServiceAgreement.lead_id.in_(lead_ids))
                .where(ServiceAgreementMessage.role == ServiceAgreementMessageRole.client)
            ).all()
            if lead_id
        }

    open_agreements: dict[uuid.UUID, str] = {}
    # Деньги по клиенту — подписанное и то, что у клиента на руках (черновики
    # и отклонённые не считаем: это ещё не деньги или уже не деньги). Нужны,
    # чтобы список можно было отсортировать по сумме, не открывая карточки.
    amounts: dict[uuid.UUID, int] = {}
    if lead_ids:
        for lead_id, status, amount_minor in db.execute(
            select(ServiceAgreement.lead_id, ServiceAgreement.status, ServiceAgreement.amount_minor)
            .where(ServiceAgreement.lead_id.in_(lead_ids))
            # Допсоглашение — не отдельные деньги: его сумма после подписи
            # становится суммой договора, и счёт дважды завысил бы итог.
            .where(ServiceAgreement.parent_agreement_id.is_(None))
            .order_by(ServiceAgreement.created_at.desc())
        ).all():
            open_agreements.setdefault(lead_id, status.value)
            if amount_minor is not None and status in _MONEY_STATUSES:
                amounts[lead_id] = amounts.get(lead_id, 0) + int(amount_minor)

    # Один клиент может вести несколько дел в разных практиках.
    areas: dict[uuid.UUID, list[str]] = {}
    practices: dict[uuid.UUID, list[str]] = {}
    intake_flags: dict[uuid.UUID, list[tuple[bool, LegalIntakeStatus]]] = {}
    if lead_ids:
        for lead_id, area, practice, without_agreement, intake_status in db.execute(
            select(
                LegalIntake.lead_id,
                LegalIntake.legal_area,
                LegalIntake.practice,
                LegalIntake.without_agreement,
                LegalIntake.status,
            ).where(LegalIntake.lead_id.in_(lead_ids))
        ).all():
            intake_flags.setdefault(lead_id, []).append((bool(without_agreement), intake_status))
            # Область права есть только у права: у инженерного обращения в
            # legal_area лежит служебное «other», и в фильтр по областям оно
            # попадать не должно.
            if practice.value == "legal":
                bucket = areas.setdefault(lead_id, [])
                if area.value not in bucket:
                    bucket.append(area.value)
            bucket = practices.setdefault(lead_id, [])
            if practice.value not in bucket:
                bucket.append(practice.value)

    # Что сейчас происходит по клиенту — одной строкой. Без неё список
    # выглядит одинаковым для того, кто ждёт договора, и того, кто уже
    # подписал, и приходится открывать каждого, чтобы вспомнить.
    return [
        {
            "lead_id": str(lead.id),
            "name": _lead_title(lead),
            "contact": lead.contact,
            "company": lead.company,
            "telegram_user_id": lead.telegram_user_id,
            "intakes": int(count),
            "last_intake_at": _iso(last_at),
            "nda_signed": lead.id in signed_nda,
            "agreement_status": open_agreements.get(lead.id),
            **case_stage.fields(
                case_stage.stage_for(
                    nda_signed=lead.id in signed_nda,
                    agreement_status=open_agreements.get(lead.id),
                    without_agreement=_worked_without_agreement(intake_flags.get(lead.id, [])),
                )
            ),
            "waiting_on_me": lead.id in awaiting_me,
            "legal_areas": areas.get(lead.id, []),
            "practices": practices.get(lead.id, []),
            "amount_minor": amounts.get(lead.id),
            # Аккаунт владельца: он проверяет систему, а не обращается.
            "is_test": is_staff(lead.telegram_user_id),
        }
        for lead, count, last_at in rows
    ]


@router.get("/clients/{lead_id}")
def client_card(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Всё по клиенту в одном ответе.

    Собирается разом, а не по частям: карточку открывают, чтобы вспомнить
    контекст перед разговором, и подгрузка блоков по очереди этому мешает.
    """
    _ = identity
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Client not found")

    intakes = db.execute(
        select(LegalIntake)
        .where(LegalIntake.lead_id == lead_id)
        .order_by(LegalIntake.created_at.desc())
    ).scalars().all()
    intake_ids = [item.id for item in intakes]

    clarifications: dict[uuid.UUID, list[dict]] = {}
    documents: dict[uuid.UUID, list[dict]] = {}
    if intake_ids:
        for row in db.execute(
            select(IntakeClarification)
            .where(IntakeClarification.intake_id.in_(intake_ids))
            .order_by(IntakeClarification.created_at)
        ).scalars().all():
            clarifications.setdefault(row.intake_id, []).append(
                {
                    "question": row.question_text,
                    "answer": row.answer_text,
                    "created_at": _iso(row.created_at),
                }
            )
        for row in db.execute(
            select(IntakeDocument)
            .where(IntakeDocument.intake_id.in_(intake_ids))
            .order_by(IntakeDocument.created_at)
        ).scalars().all():
            documents.setdefault(row.intake_id, []).append(
                {
                    "document_id": str(row.id),
                    "telegram_file_id": row.telegram_file_id,
                    "file_name": row.file_name,
                    "file_size": row.file_size,
                    "mime_type": row.mime_type,
                    "nda_signed_at_upload": row.nda_signed_at_upload,
                    "created_at": _iso(row.created_at),
                }
            )

    nda_checks = [NdaSignature.lead_id == lead_id]
    if lead.telegram_user_id is not None:
        nda_checks.append(NdaSignature.telegram_user_id == lead.telegram_user_id)
    nda = db.execute(
        select(NdaSignature)
        .where(or_(*nda_checks))
        .order_by(NdaSignature.signed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    nda_consent = (
        db.get(NdaPersonalDataConsent, nda.pdn_consent_id)
        if nda and nda.pdn_consent_id
        else None
    )

    agreements = db.execute(
        select(ServiceAgreement)
        .where(ServiceAgreement.lead_id == lead_id)
        .order_by(ServiceAgreement.created_at.desc())
    ).scalars().all()

    messages: dict[uuid.UUID, list[dict]] = {}
    if agreements:
        for row in db.execute(
            select(ServiceAgreementMessage)
            .where(ServiceAgreementMessage.agreement_id.in_([a.id for a in agreements]))
            .order_by(ServiceAgreementMessage.created_at)
        ).scalars().all():
            messages.setdefault(row.agreement_id, []).append(
                {
                    "role": row.role.value,
                    "text": row.text,
                    "created_at": _iso(row.created_at),
                }
            )

    acts: dict[uuid.UUID, list[dict]] = {}
    if agreements:
        for act in db.execute(
            select(WorkAct)
            .where(WorkAct.agreement_id.in_([a.id for a in agreements]))
            .order_by(WorkAct.created_at.desc())
        ).scalars().all():
            acts.setdefault(act.agreement_id, []).append(
                {
                    "act_id": str(act.id),
                    "act_number": act.act_number,
                    "status": act.status.value,
                    "description_text": act.description_text,
                    "amount_minor": act.amount_minor,
                    "currency": act.currency,
                    "created_at": _iso(act.created_at),
                    "sent_at": _iso(act.sent_at),
                    "claimed_paid_at": _iso(act.claimed_paid_at),
                    "paid_at": _iso(act.paid_at),
                    "paid_note": act.paid_note,
                    "last_reminded_at": _iso(act.last_reminded_at),
                }
            )

    # Допсоглашения — под своим договором, а не отдельной строкой: иначе на
    # экране они выглядят вторым договором, а этап считался бы по ним.
    supplements: dict[uuid.UUID, list[ServiceAgreement]] = {}
    for item in agreements:
        if item.parent_agreement_id is not None:
            supplements.setdefault(item.parent_agreement_id, []).append(item)
    agreements = [item for item in agreements if item.parent_agreement_id is None]

    def _agreement_row(item: ServiceAgreement) -> dict:
        return {
            "agreement_id": str(item.id),
            # Без этого при втором обращении клиента нельзя понять, к чему
            # относится договор: на экране они лежат одним списком.
            "intake_id": str(item.intake_id) if item.intake_id else None,
            "parent_agreement_id": str(item.parent_agreement_id) if item.parent_agreement_id else None,
            "number": item.agreement_number,
            "status": item.status.value,
            "template_kind": item.template_kind.value,
            "revision": item.revision,
            "subject": item.subject,
            "price_text": item.price_text,
            "amount_minor": item.amount_minor,
            "currency": item.currency,
            "payment_terms": item.payment_terms,
            "scope_text": item.scope_text,
            "exclusions_text": item.exclusions_text,
            "schedule_text": item.schedule_text,
            "expires_at": _iso(item.expires_at),
            "created_at": _iso(item.created_at),
            "sent_at": _iso(item.sent_at),
            "viewed_at": _iso(item.viewed_at),
            "last_reminded_at": _iso(item.last_reminded_at),
            "signed_at": _iso(item.signed_at),
            "declined_at": _iso(item.declined_at),
            # Клиент называет причину, когда отклоняет, — она писалась в
            # базу и нигде не читалась: юрист видел только дату отказа.
            "decline_reason": item.decline_reason,
            # Реквизиты, которые клиент ввёл при подписании: юристу они
            # нужны так же, как условия, — по ним видно, с кем договор.
            "client_snapshot": item.client_snapshot or {},
            "signer_position": item.signer_position,
            "authority_basis": item.authority_basis,
            "document_version": item.document_version,
            "messages": messages.get(item.id, []),
            "acts": acts.get(item.id, []),
            "supplements": [_agreement_row(row) for row in supplements.get(item.id, [])],
        }

    latest_agreement = agreements[0] if agreements else None
    # Договоры уже новыми вперёд: первый встреченный по обращению — последний.
    latest_by_intake: dict[uuid.UUID, ServiceAgreement] = {}
    for item in agreements:
        if item.intake_id is not None:
            latest_by_intake.setdefault(item.intake_id, item)
    return {
        "lead_id": str(lead.id),
        "name": _lead_title(lead),
        # Карточку архивного клиента открывают из архива — там свои кнопки.
        "archived_at": _iso(lead.archived_at),
        "is_test": is_staff(lead.telegram_user_id),
        **case_stage.fields(
            case_stage.stage_for(
                nda_signed=nda is not None,
                agreement_status=latest_agreement.status.value if latest_agreement else None,
                without_agreement=_worked_without_agreement(
                    [(item.without_agreement, item.status) for item in intakes]
                ),
            )
        ),
        "contact": lead.contact,
        "company": lead.company,
        "email": lead.email,
        "phone": lead.phone,
        "telegram_user_id": lead.telegram_user_id,
        "source": lead.source.value if lead.source else None,
        "created_at": _iso(lead.created_at),
        "nda": (
            {
                "signed_at": _iso(nda.signed_at),
                "signer_full_name": nda.signer_full_name,
                "signer_contact": nda.signer_contact,
                "signer_org": nda.signer_org,
                "identity_document_provided": bool(nda.signer_identity_document),
                "pdn_consent_at": _iso(nda_consent.accepted_at) if nda_consent else None,
                "pdn_consent_version": nda_consent.document_version if nda_consent else None,
                "pdn_consent_id": str(nda_consent.id) if nda_consent else None,
                "version": nda.document_version,
                "nda_id": str(nda.id),
            }
            if nda
            else None
        ),
        "intakes": [
            {
                "intake_id": str(item.id),
                "created_at": _iso(item.created_at),
                "legal_area": item.legal_area.value,
                "practice": item.practice.value,
                "category": item.category,
                "client_type": item.client_type.value,
                "urgency": item.urgency.value,
                "deadline": item.deadline,
                "deadline_at": _iso(item.deadline_at),
                "region": item.region,
                "status": item.status.value,
                "conflict_status": item.conflict_status.value,
                "description": item.description,
                "internal_note": item.internal_note,
                "without_agreement": item.without_agreement,
                "outreach_sent_at": _iso(item.outreach_sent_at),
                "outreach_blocked_reason": item.outreach_blocked_reason,
                "clarifications": clarifications.get(item.id, []),
                "documents": documents.get(item.id, []),
                "links": _intake_links_for(db, item.id),
                # У постоянного клиента с двумя делами этап в шапке — по
                # последнему договору; у каждого обращения — свой, по его договорам.
                **case_stage.fields(
                    case_stage.stage_for(
                        nda_signed=nda is not None,
                        agreement_status=latest_by_intake[item.id].status.value
                        if item.id in latest_by_intake
                        else None,
                        without_agreement=item.without_agreement,
                    )
                ),
            }
            for item in intakes
        ],
        "agreements": [_agreement_row(item) for item in agreements],
    }


@router.get("/agreements/{agreement_id}/document")
def agreement_document(
    agreement_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Точный текст, который видел и подписывал клиент, и его хеш.

    Карточка показывает условия по полям — это реконструкция. При споре о
    содержании нужна не она, а сам документ: хеш здесь и есть то, под чем
    клиент поставил подпись, и без текста рядом он ничего не доказывает.
    Отдаётся отдельно: текст длинный, а нужен редко.
    """
    _ = identity
    item = db.get(ServiceAgreement, agreement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
    return {
        "agreement_id": str(item.id),
        "number": item.agreement_number,
        "document_version": item.document_version,
        "document_hash": item.document_hash,
        "document_text": item.document_text,
    }


@router.get("/nda/{nda_id}/document")
def nda_document(
    nda_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """То же для соглашения о конфиденциальности."""
    _ = identity
    item = db.get(NdaSignature, nda_id)
    if item is None:
        raise HTTPException(status_code=404, detail="NDA not found")
    return {
        "nda_id": str(item.id),
        "document_version": item.document_version,
        "document_hash": item.document_hash,
        "document_text": item.document_text,
    }


@router.get("/nda-consents/{consent_id}/document")
def nda_consent_document(
    consent_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Точный отдельный текст согласия на обработку персональных данных."""
    _ = identity
    item = db.get(NdaPersonalDataConsent, consent_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Consent not found")
    return {
        "consent_id": str(item.id),
        "document_version": item.document_version,
        "document_hash": item.document_hash,
        "document_text": item.document_text,
        "accepted_at": _iso(item.accepted_at),
        "revoked_at": _iso(item.revoked_at),
    }


# Практика в Москве: «этот месяц» считается по московской полуночи, иначе
# подпись в час ночи первого числа уезжала бы в прошлый месяц.
_PRACTICE_TZ = ZoneInfo("Europe/Moscow")

# Статусы, по которым сумма ещё может стать деньгами.
_PIPELINE_STATUSES = (ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed)
# Что считается деньгами клиента в списке: подписано или лежит у клиента.
_MONEY_STATUSES = (ServiceAgreementStatus.signed, *_PIPELINE_STATUSES)


def _month_start(now: datetime, months_back: int = 0) -> datetime:
    local = now.astimezone(_PRACTICE_TZ)
    year, month = local.year, local.month - months_back
    while month < 1:
        month += 12
        year -= 1
    return datetime(year, month, 1, tzinfo=_PRACTICE_TZ).astimezone(timezone.utc)


def _not_archived_agreement():
    """Договор, который идёт в деньги: не архивного клиента и не теста с
    аккаунта владельца. NOT IN по NULL дал бы NULL — договор без клиента
    выпал бы из итогов, поэтому он оговорён отдельно."""
    hidden = select(Lead.id).where(Lead.archived_at.is_not(None))
    staff = staff_telegram_ids()
    if staff:
        hidden = select(Lead.id).where(or_(Lead.archived_at.is_not(None), Lead.telegram_user_id.in_(staff)))
    return or_(ServiceAgreement.lead_id.is_(None), ServiceAgreement.lead_id.not_in(hidden))


_ACT_LIVE = (WorkActStatus.sent, WorkActStatus.claimed_paid, WorkActStatus.paid)
_ACT_OPEN = (WorkActStatus.sent, WorkActStatus.claimed_paid)


def _counted_acts():
    """Акты, которые идут в деньги: не отозванные, не архивных клиентов и не тесты."""
    return (
        select(WorkAct, Lead)
        .outerjoin(Lead, Lead.id == WorkAct.lead_id)
        .where(WorkAct.cancelled_at.is_(None))
        .where(Lead.archived_at.is_(None))
        .where(real_client(Lead.telegram_user_id))
    )


def _act_bucket(rows) -> dict:
    return {"count": len(rows), "minor": sum(int(act.amount_minor or 0) for act, _ in rows)}


def _overdue(act: WorkAct, now: datetime) -> bool:
    """Просрочен: ждёт оплаты, клиент не сказал «оплатил», срок с отправки вышел."""
    days = max(get_settings().act_payment_days, 1)
    return (
        act.status == WorkActStatus.sent
        and act.sent_at is not None
        and act.sent_at < now - timedelta(days=days)
    )


def _acts_summary(db: Session, now: datetime, this_month: datetime) -> dict:
    rows = db.execute(_counted_acts().where(WorkAct.status.in_(_ACT_LIVE))).all()
    issued = [r for r in rows if r[0].sent_at and r[0].sent_at >= this_month]
    paid = [r for r in rows if r[0].status == WorkActStatus.paid and r[0].paid_at and r[0].paid_at >= this_month]
    open_rows = [r for r in rows if r[0].status in _ACT_OPEN]
    overdue = [r for r in open_rows if _overdue(r[0], now)]
    claimed = [r for r in open_rows if r[0].status == WorkActStatus.claimed_paid]
    open_rows.sort(key=lambda r: r[0].sent_at or now)
    return {
        "payment_days": max(get_settings().act_payment_days, 1),
        "issued_this_month": _act_bucket(issued),
        "paid_this_month": _act_bucket(paid),
        "receivable": _act_bucket(open_rows),
        "overdue": _act_bucket(overdue),
        "claimed": _act_bucket(claimed),
        "open": [
            {
                "act_id": str(act.id),
                "act_number": act.act_number,
                "lead_id": str(act.lead_id) if act.lead_id else None,
                "client": _lead_title(lead),
                "amount_minor": act.amount_minor,
                "status": act.status.value,
                "sent_at": _iso(act.sent_at),
                "claimed_paid_at": _iso(act.claimed_paid_at),
                "last_reminded_at": _iso(act.last_reminded_at),
                "days_since_sent": _days_since(act.sent_at),
                "overdue": _overdue(act, now),
            }
            for act, lead in open_rows[:100]
        ],
    }


def _sum_and_count(db: Session, *conditions) -> dict:
    """Сумма и число договоров; отдельно — сколько из них без суммы.

    SUM пропускает NULL молча, и итог выглядел бы полным, когда он неполный.
    Число «без суммы» — это честное предупреждение рядом с цифрой.
    """
    row = db.execute(
        select(
            func.count(ServiceAgreement.id),
            func.coalesce(func.sum(ServiceAgreement.amount_minor), 0),
            func.count(ServiceAgreement.id).filter(ServiceAgreement.amount_minor.is_(None)),
        )
        # Допсоглашение не отдельная сделка: его сумма уже в сумме договора.
        .where(ServiceAgreement.parent_agreement_id.is_(None))
        .where(_not_archived_agreement())
        .where(*conditions)
    ).one()
    return {"count": int(row[0]), "minor": int(row[1]), "unpriced": int(row[2])}


@router.get("/finance")
def finance(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Деньги практики одним взглядом: сколько подписано, сколько в работе.

    До этого сумма существовала только текстом внутри карточки одного клиента —
    «сколько за месяц» нельзя было посчитать даже вручную по экрану.
    """
    _ = identity
    now = datetime.now(timezone.utc)
    this_month = _month_start(now)
    prev_month = _month_start(now, 1)
    signed = ServiceAgreement.status == ServiceAgreementStatus.signed

    rows = db.execute(
        select(ServiceAgreement, Lead)
        .outerjoin(Lead, Lead.id == ServiceAgreement.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(ServiceAgreement.status != ServiceAgreementStatus.superseded)
        .where(ServiceAgreement.parent_agreement_id.is_(None))
        .where(real_client(Lead.telegram_user_id))
        .order_by(ServiceAgreement.created_at.desc())
        .limit(200)
    ).all()

    signed_total = _sum_and_count(db, signed)
    priced_signed = signed_total["count"] - signed_total["unpriced"]
    acts = _acts_summary(db, now, this_month)

    return {
        "generated_at": _iso(now),
        "currency": "RUB",
        "month_from": _iso(this_month),
        "signed_this_month": _sum_and_count(db, signed, ServiceAgreement.signed_at >= this_month),
        "signed_prev_month": _sum_and_count(
            db,
            signed,
            ServiceAgreement.signed_at >= prev_month,
            ServiceAgreement.signed_at < this_month,
        ),
        "signed_total": signed_total,
        "average_signed_minor": (
            signed_total["minor"] // priced_signed if priced_signed else None
        ),
        "in_pipeline": _sum_and_count(db, ServiceAgreement.status.in_(_PIPELINE_STATUSES)),
        "drafts": _sum_and_count(db, ServiceAgreement.status == ServiceAgreementStatus.draft),
        "declined_this_month": _sum_and_count(
            db,
            ServiceAgreement.status == ServiceAgreementStatus.declined,
            ServiceAgreement.declined_at >= this_month,
        ),
        # По актам: сколько выставлено и оплачено, кто должен и кто просрочил.
        # Подписанный договор — ещё не деньги; деньги — оплаченный акт.
        "acts": acts,
        "agreements": [
            {
                "agreement_id": str(a.id),
                "lead_id": str(a.lead_id) if a.lead_id else None,
                "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                "number": a.agreement_number,
                "subject": a.subject[:160],
                "status": a.status.value,
                "amount_minor": a.amount_minor,
                "price_text": a.price_text,
                "signed_at": _iso(a.signed_at),
                "sent_at": _iso(a.sent_at),
                "created_at": _iso(a.created_at),
            }
            for a, lead in rows
        ],
    }


@router.get("/funnel")
def funnel(
    days: int = Query(default=90, ge=7, le=730),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Откуда приходят клиенты и на каком шаге останавливаются (см. practice_funnel)."""
    _ = identity
    now = datetime.now(timezone.utc)
    result = practice_funnel.build(db, since=practice_funnel.period_start(now, days), now=now)
    return {"days": days, **result}


class AmountPatch(BaseModel):
    amount_minor: int | None = Field(default=None, ge=0, le=10**13)


@router.patch("/agreements/{agreement_id}/amount")
def set_agreement_amount(
    agreement_id: uuid.UUID,
    payload: AmountPatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Сумма к учёту — только дозаполнить пустую.

    Нужна договорам, составленным до того, как сумма появилась числом:
    иначе итоги молча неполные. Поменять уже указанную сумму отсюда нельзя —
    это было бы решение одной стороны. Неподписанный договор меняется новой
    редакцией, подписанный — допсоглашением, которое подписывает клиент.
    """
    item = db.get(ServiceAgreement, agreement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if item.parent_agreement_id is not None:
        raise HTTPException(status_code=409, detail="Supplement amount is set by its document")
    if item.amount_minor is not None:
        raise HTTPException(
            status_code=409,
            detail="Amount is already set; change it with a new revision or a supplementary agreement",
        )
    before = item.amount_minor
    item.amount_minor = payload.amount_minor
    db.add(item)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="service_agreement.amount",
        target_type="service_agreement",
        target_id=item.id,
        details={"from": before, "to": payload.amount_minor},
    )
    db.commit()
    return {
        "agreement_id": str(item.id),
        "amount_minor": item.amount_minor,
        "currency": item.currency,
    }


@router.get("/clients/{lead_id}/history")
def client_history(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=300),
) -> dict:
    """Что и когда происходило с клиентом — из журнала, который уже писался.

    Карточка показывает только текущее состояние. Кто отправил договор,
    когда клиент его открыл, когда подписал и почему сорвалось — всё это
    записывалось при каждом действии и ни разу не читалось обратно.
    Отдаётся отдельно от карточки: длинно, а нужно не всякий раз.
    """
    _ = identity
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Client not found")

    intake_ids = select(LegalIntake.id).where(LegalIntake.lead_id == lead_id)
    agreements = {
        a.id: a.agreement_number
        for a in db.execute(
            select(ServiceAgreement).where(ServiceAgreement.lead_id == lead_id)
        ).scalars()
    }

    rows = db.execute(
        select(AuditLog)
        .where(
            or_(
                and_(AuditLog.target_type == "legal_intake", AuditLog.target_id.in_(intake_ids)),
                and_(
                    AuditLog.target_type == "service_agreement",
                    AuditLog.target_id.in_(list(agreements) or [uuid.UUID(int=0)]),
                ),
                and_(AuditLog.target_type == "lead", AuditLog.target_id == lead_id),
            )
        )
        # created_at — это now() на момент начала транзакции: у записей одного
        # запроса оно совпадает. Второй ключ делает порядок стабильным.
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    ).scalars().all()

    return {
        "lead_id": str(lead_id),
        "items": [
            {
                "at": _iso(row.created_at),
                "action": row.action,
                "target_type": row.target_type,
                "target_id": str(row.target_id) if row.target_id else None,
                # Номер договора — чтобы в ленте было видно, о какой редакции речь.
                "agreement_number": agreements.get(row.target_id),
                "details": row.details or {},
            }
            for row in rows
        ],
    }


@router.get("/documents/{document_id}")
def document_meta(
    document_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Где лежит присланный клиентом файл.

    Сам файл живёт в Telegram: здесь хранится только его идентификатор, а
    достать байты может лишь бот своим токеном. Веб-слой берёт отсюда
    идентификатор по номеру документа, а не принимает его от браузера: так
    файл можно получить только для документа, который есть в базе.
    """
    _ = identity
    row = db.get(IntakeDocument, document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    intake = db.get(LegalIntake, row.intake_id)
    return {
        "document_id": str(row.id),
        "intake_id": str(row.intake_id),
        "lead_id": str(intake.lead_id) if intake else None,
        "telegram_file_id": row.telegram_file_id,
        "file_name": row.file_name,
        "file_size": row.file_size,
        "mime_type": row.mime_type,
        "created_at": _iso(row.created_at),
    }


class IntakeLinkCreate(BaseModel):
    linked_intake_id: uuid.UUID | None = None
    linked_lead_id: uuid.UUID
    # Роль обращения из URL относительно связываемого — не тип связи как
    # таковой: "main"/"subordinate" описывают одну и ту же связь с разных
    # концов, а хранится она всегда как subordinate → main (см. IntakeLink).
    role: str
    note: str | None = Field(default=None, max_length=500)


_INTAKE_LINK_ROLES = {"main", "subordinate", "joint"}


@router.post("/intakes/{intake_id}/links")
def create_intake_link(
    intake_id: uuid.UUID,
    payload: IntakeLinkCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Пометить обращение как связанное с делом другого клиента.

    Найдено вживую: два обращения оказались одним и тем же имущественным
    спором с двух сторон, а проверка конфликта у каждого шла независимо.
    Связь — только пометка для контекста: договоры, NDA и документы каждого
    обращения остаются раздельными, это не слияние дел в одно.
    """
    intake = db.get(LegalIntake, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="Intake not found")

    if payload.role not in _INTAKE_LINK_ROLES:
        raise HTTPException(status_code=400, detail="Неизвестная роль связи")

    query = select(LegalIntake).where(LegalIntake.lead_id == payload.linked_lead_id)
    if payload.linked_intake_id:
        query = query.where(LegalIntake.id == payload.linked_intake_id)
    matches = db.scalars(query.limit(2)).all()
    if len(matches) > 1:
        raise HTTPException(status_code=409, detail="У клиента несколько обращений: выберите конкретное дело")
    linked_intake = matches[0] if matches else None
    if linked_intake is None:
        raise HTTPException(status_code=404, detail="У указанного клиента нет обращения")
    if linked_intake.id == intake_id:
        raise HTTPException(status_code=400, detail="Нельзя связать обращение само с собой")

    existing = db.execute(
        select(IntakeLink).where(
            or_(
                and_(
                    IntakeLink.intake_id == intake_id,
                    IntakeLink.linked_intake_id == linked_intake.id,
                ),
                and_(
                    IntakeLink.intake_id == linked_intake.id,
                    IntakeLink.linked_intake_id == intake_id,
                ),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Эти обращения уже связаны — сначала снимите старую связь"
        )

    # role="main" переворачивает пару: обращение из URL становится основным,
    # значит подчинённым (первым в строке) хранится связываемое.
    if payload.role == "main":
        row_intake_id, row_linked_intake_id = linked_intake.id, intake_id
        link_type = IntakeLinkType.subordinate
    elif payload.role == "subordinate":
        row_intake_id, row_linked_intake_id = intake_id, linked_intake.id
        link_type = IntakeLinkType.subordinate
    else:
        row_intake_id, row_linked_intake_id = intake_id, linked_intake.id
        link_type = IntakeLinkType.joint

    link = IntakeLink(
        intake_id=row_intake_id,
        linked_intake_id=row_linked_intake_id,
        link_type=link_type,
        note=(payload.note or "").strip() or None,
    )
    db.add(link)
    db.flush()
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="intake_link.create",
        target_type="legal_intake",
        target_id=intake_id,
        details={"linked_intake_id": str(linked_intake.id), "role": payload.role},
    )
    db.commit()
    return {"link_id": str(link.id)}


@router.delete("/intakes/links/{link_id}")
def delete_intake_link(
    link_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Снять связь. Обе стороны равноправны — годится id связи с любого конца."""
    link = db.get(IntakeLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="intake_link.delete",
        target_type="legal_intake",
        target_id=link.intake_id,
        details={"linked_intake_id": str(link.linked_intake_id), "link_type": link.link_type.value},
    )
    db.delete(link)
    db.commit()
    return {"ok": True}


# --- Архив клиентов -------------------------------------------------------
#
# «Удалить» в карточке — не удаление, а архив: клиент пропадает из списка,
# задач и денег, но из архива его можно вернуть. Удалить совсем можно только
# из архива — два шага, чтобы подписанный договор не исчез от одного касания.


def _client_footprint(db: Session, lead_id: uuid.UUID) -> dict:
    """Что лежит у клиента — чтобы перед удалением было видно, что пропадёт."""
    intake_ids = select(LegalIntake.id).where(LegalIntake.lead_id == lead_id)
    agreements = db.execute(
        select(ServiceAgreement.status, ServiceAgreement.parent_agreement_id).where(
            or_(ServiceAgreement.lead_id == lead_id, ServiceAgreement.intake_id.in_(intake_ids))
        )
    ).all()
    main = [status for status, parent in agreements if parent is None]
    return {
        "intakes": int(db.scalar(select(func.count()).select_from(intake_ids.subquery())) or 0),
        "agreements": len([s for s in main if s != ServiceAgreementStatus.superseded]),
        "signed_agreements": len([s for s in main if s == ServiceAgreementStatus.signed]),
        "acts": int(
            db.scalar(
                select(func.count(WorkAct.id))
                .join(ServiceAgreement, ServiceAgreement.id == WorkAct.agreement_id)
                .where(or_(ServiceAgreement.lead_id == lead_id, ServiceAgreement.intake_id.in_(intake_ids)))
            )
            or 0
        ),
        "nda_signed": db.scalar(select(func.count(NdaSignature.id)).where(NdaSignature.lead_id == lead_id)) > 0,
    }


def _lead_or_404(db: Session, lead_id: uuid.UUID) -> Lead:
    lead = db.execute(select(Lead).where(Lead.id == lead_id).with_for_update()).scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return lead


@router.get("/archive")
def archive(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Клиенты в архиве — последние убранные первыми."""
    _ = identity
    leads = db.scalars(
        select(Lead).where(Lead.archived_at.is_not(None)).order_by(Lead.archived_at.desc()).limit(200)
    ).all()
    return [
        {
            "lead_id": str(lead.id),
            "name": _lead_title(lead),
            "contact": lead.contact,
            "company": lead.company,
            "created_at": _iso(lead.created_at),
            "archived_at": _iso(lead.archived_at),
            "is_test": is_staff(lead.telegram_user_id),
            **_client_footprint(db, lead.id),
        }
        for lead in leads
    ]


@router.post("/clients/{lead_id}/archive")
def archive_client(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    lead = _lead_or_404(db, lead_id)
    if lead.archived_at is None:
        lead.archived_at = datetime.now(timezone.utc)
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="lead.archive",
            target_type="lead",
            target_id=lead.id,
            details={},
        )
        db.commit()
    return {"lead_id": str(lead.id), "archived_at": _iso(lead.archived_at)}


@router.post("/clients/{lead_id}/restore")
def restore_client(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    lead = _lead_or_404(db, lead_id)
    if lead.archived_at is not None:
        lead.archived_at = None
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="lead.restore",
            target_type="lead",
            target_id=lead.id,
            details={"reason": "lawyer"},
        )
        db.commit()
    return {"lead_id": str(lead.id), "archived_at": None}


@router.delete("/clients/{lead_id}")
def purge_client(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Удалить клиента совсем — только из архива.

    Уходит всё, что относится к этому клиенту: обращения с уточнениями,
    документами и связями, договоры с допсоглашениями, перепиской и актами,
    NDA и согласие на обработку ПД, события, заказы консультаций и записи
    журнала о нём. Записи другого клиента с тем же Telegram не трогаются —
    удаляется только то, что привязано к этой карточке.

    В журнале остаётся одна запись — что клиент удалён и сколько чего было,
    без имени и контактов: иначе удаление было бы неполным.
    """
    lead = _lead_or_404(db, lead_id)
    if lead.archived_at is None:
        raise HTTPException(status_code=409, detail="Move the client to the archive first")

    footprint = _client_footprint(db, lead.id)
    intake_ids = list(db.scalars(select(LegalIntake.id).where(LegalIntake.lead_id == lead.id)))
    agreement_ids = list(
        db.scalars(
            select(ServiceAgreement.id).where(
                or_(
                    ServiceAgreement.lead_id == lead.id,
                    ServiceAgreement.intake_id.in_(intake_ids or [uuid.UUID(int=0)]),
                )
            )
        )
    )
    act_ids = list(
        db.scalars(select(WorkAct.id).where(WorkAct.agreement_id.in_(agreement_ids or [uuid.UUID(int=0)])))
    )
    order_ids = list(
        db.scalars(select(SpecialConsultationOrder.id).where(SpecialConsultationOrder.lead_id == lead.id))
    )
    none = [uuid.UUID(int=0)]

    db.execute(
        delete(AuditLog).where(
            or_(
                and_(AuditLog.target_type == "lead", AuditLog.target_id == lead.id),
                and_(AuditLog.target_type == "legal_intake", AuditLog.target_id.in_(intake_ids or none)),
                and_(AuditLog.target_type == "service_agreement", AuditLog.target_id.in_(agreement_ids or none)),
                and_(AuditLog.target_type == "work_act", AuditLog.target_id.in_(act_ids or none)),
                and_(
                    AuditLog.target_type == "special_consultation_order",
                    AuditLog.target_id.in_(order_ids or none),
                ),
            )
        )
    )
    if agreement_ids:
        # Акты и переписка уходят каскадом, допсоглашения — по ссылке на договор.
        db.execute(delete(WorkAct).where(WorkAct.agreement_id.in_(agreement_ids)))
        db.execute(delete(ServiceAgreementMessage).where(ServiceAgreementMessage.agreement_id.in_(agreement_ids)))
        db.execute(delete(ServiceAgreement).where(ServiceAgreement.id.in_(agreement_ids)))
    if order_ids:
        db.execute(delete(SpecialConsultationPayment).where(SpecialConsultationPayment.order_id.in_(order_ids)))
        db.execute(delete(SpecialConsultationOrder).where(SpecialConsultationOrder.id.in_(order_ids)))
    db.execute(delete(Event).where(Event.lead_id == lead.id))
    # Задания другого продукта (анализ договоров) не наши — только отвязываем.
    db.execute(update(ContractJob).where(ContractJob.lead_id == lead.id).values(lead_id=None))
    # NDA и согласие, обращения с уточнениями, документами и связями —
    # каскадом от клиента.
    db.execute(delete(NdaSignature).where(NdaSignature.lead_id == lead.id))
    db.execute(delete(NdaPersonalDataConsent).where(NdaPersonalDataConsent.lead_id == lead.id))
    db.execute(delete(LegalIntake).where(LegalIntake.lead_id == lead.id))
    db.execute(delete(Lead).where(Lead.id == lead.id))
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="lead.purge",
        target_type="lead",
        target_id=lead_id,
        details=footprint,
    )
    db.commit()
    return {"lead_id": str(lead_id), "deleted": footprint}


# --- Не доставлено в Telegram -----------------------------------------------


@router.post("/deliveries/{delivery_id}/retry")
def retry_delivery(
    delivery_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
) -> dict:
    """Повторить уведомление сейчас. Договор, ответ и акт так не повторяются:
    их отправляют из карточки, чтобы клиент не получил дубль."""
    _ = identity
    status = telegram_delivery.retry_now(delivery_id)
    if status == "missing":
        raise HTTPException(status_code=404, detail="Delivery not found")
    if status == "not_retryable":
        raise HTTPException(status_code=409, detail="Send it again from the client card")
    return {"delivery_id": str(delivery_id), "status": status}


@router.post("/deliveries/{delivery_id}/dismiss")
def dismiss_delivery(
    delivery_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Убрать из «Не доставлено»: отправка потеряла смысл."""
    _ = identity
    row = db.get(TelegramDelivery, delivery_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    row.dismissed_at = row.dismissed_at or datetime.now(timezone.utc)
    if row.status == "pending":
        row.status = "failed"
        row.next_attempt_at = None
    db.commit()
    return {"delivery_id": str(delivery_id), "dismissed": True}
