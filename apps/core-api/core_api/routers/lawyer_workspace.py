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
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import (
    ActorType,
    IntakeClarification,
    IntakeDocument,
    Lead,
    LegalIntake,
    LegalIntakeStatus,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
    ServiceAgreementStatus,
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


def _stage_for(*, nda_signed: bool, agreement_status: str | None) -> str:
    """Этап дела одной фразой — то, что юрист хочет увидеть, не открывая карточку."""
    if agreement_status == "signed":
        return "Договор подписан"
    if agreement_status in {"sent", "viewed"}:
        return "Договор у клиента"
    if agreement_status == "draft":
        return "Договор не отправлен"
    if agreement_status == "declined":
        return "Клиент отказался"
    if nda_signed:
        return "Готовим условия"
    return "Первичное обращение"


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
        .where(ServiceAgreementMessage.role == ServiceAgreementMessageRole.client)
        .order_by(ServiceAgreementMessage.created_at)
    ).all()

    # 3. До клиента не дозвонились: заявка пришла не из Telegram либо бот
    #    заблокирован. Написать первым он не может — нужен человек.
    unreachable = db.execute(
        select(LegalIntake, Lead)
        .join(Lead, Lead.id == LegalIntake.lead_id)
        .where(LegalIntake.outreach_blocked_reason.is_not(None))
        .where(LegalIntake.status.not_in([LegalIntakeStatus.closed, LegalIntakeStatus.declined]))
        .order_by(LegalIntake.created_at)
    ).all()

    # 4. Договор отправлен, но клиент молчит несколько дней.
    awaiting = db.execute(
        select(ServiceAgreement, Lead)
        .outerjoin(Lead, Lead.id == ServiceAgreement.lead_id)
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

    # 5. Обращение без договора: диалог прошёл, а условия не предложены.
    with_agreement = select(ServiceAgreement.intake_id).where(
        ServiceAgreement.intake_id.is_not(None)
    )
    no_agreement = db.execute(
        select(LegalIntake, Lead)
        .join(Lead, Lead.id == LegalIntake.lead_id)
        .where(LegalIntake.id.not_in(with_agreement))
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
        .where(LegalIntake.deadline_at.is_not(None))
        .where(LegalIntake.deadline_at < now + timedelta(days=_DEADLINE_SOON_DAYS))
        .where(LegalIntake.status.not_in([LegalIntakeStatus.closed, LegalIntakeStatus.declined]))
        .order_by(LegalIntake.deadline_at)
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
                        "contact": lead.contact,
                        "reason": i.outreach_blocked_reason,
                        "created_at": _iso(i.created_at),
                        "days_waiting": _days_since(i.created_at),
                    }
                    for i, lead in unreachable
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
                        "subject": a.subject[:160],
                        "status": a.status.value,
                        "sent_at": _iso(a.sent_at),
                        "days_waiting": _days_since(a.sent_at),
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
                        "legal_area": i.legal_area.value,
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
                        "legal_area": i.legal_area.value,
                        "status": i.status.value,
                        "urgency": i.urgency.value,
                        "created_at": _iso(i.created_at),
                        "days_waiting": _days_since(i.created_at),
                    }
                    for i, lead in no_agreement
                ],
            },
        ],
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
        .group_by(Lead.id)
        .order_by(func.max(LegalIntake.created_at).desc())
        .limit(limit)
    )
    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.where(
            or_(
                Lead.name.ilike(pattern),
                Lead.contact.ilike(pattern),
                Lead.company.ilike(pattern),
            )
        )

    rows = db.execute(query).all()
    lead_ids = [lead.id for lead, _, _ in rows]

    signed_nda = set(
        db.execute(
            select(NdaSignature.lead_id).where(NdaSignature.lead_id.in_(lead_ids))
        ).scalars().all()
    ) if lead_ids else set()

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
    if lead_ids:
        for lead_id, status in db.execute(
            select(ServiceAgreement.lead_id, ServiceAgreement.status)
            .where(ServiceAgreement.lead_id.in_(lead_ids))
            .order_by(ServiceAgreement.created_at.desc())
        ).all():
            open_agreements.setdefault(lead_id, status.value)

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
            "stage": _stage_for(
                nda_signed=lead.id in signed_nda,
                agreement_status=open_agreements.get(lead.id),
            ),
            "waiting_on_me": lead.id in awaiting_me,
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
                    "telegram_file_id": row.telegram_file_id,
                    "file_name": row.file_name,
                    "file_size": row.file_size,
                    "mime_type": row.mime_type,
                    "nda_signed_at_upload": row.nda_signed_at_upload,
                    "created_at": _iso(row.created_at),
                }
            )

    nda = db.execute(
        select(NdaSignature).where(NdaSignature.lead_id == lead_id)
    ).scalar_one_or_none()

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

    latest_agreement = agreements[0] if agreements else None
    return {
        "lead_id": str(lead.id),
        "name": _lead_title(lead),
        "stage": _stage_for(
            nda_signed=nda is not None,
            agreement_status=latest_agreement.status.value if latest_agreement else None,
        ),
        "contact": lead.contact,
        "company": lead.company,
        "telegram_user_id": lead.telegram_user_id,
        "source": lead.source.value if lead.source else None,
        "created_at": _iso(lead.created_at),
        "nda": (
            {
                "signed_at": _iso(nda.signed_at),
                "signer_full_name": nda.signer_full_name,
                "signer_contact": nda.signer_contact,
                "signer_org": nda.signer_org,
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
                "client_type": item.client_type.value,
                "urgency": item.urgency.value,
                "deadline": item.deadline,
                "deadline_at": _iso(item.deadline_at),
                "region": item.region,
                "status": item.status.value,
                "conflict_status": item.conflict_status.value,
                "description": item.description,
                "internal_note": item.internal_note,
                "outreach_sent_at": _iso(item.outreach_sent_at),
                "outreach_blocked_reason": item.outreach_blocked_reason,
                "clarifications": clarifications.get(item.id, []),
                "documents": documents.get(item.id, []),
            }
            for item in intakes
        ],
        "agreements": [
            {
                "agreement_id": str(item.id),
                # Без этого при втором обращении клиента нельзя понять, к чему
                # относится договор: на экране они лежат одним списком.
                "intake_id": str(item.intake_id) if item.intake_id else None,
                "number": item.agreement_number,
                "status": item.status.value,
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
            }
            for item in agreements
        ],
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


# Практика в Москве: «этот месяц» считается по московской полуночи, иначе
# подпись в час ночи первого числа уезжала бы в прошлый месяц.
_PRACTICE_TZ = ZoneInfo("Europe/Moscow")

# Статусы, по которым сумма ещё может стать деньгами.
_PIPELINE_STATUSES = (ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed)


def _month_start(now: datetime, months_back: int = 0) -> datetime:
    local = now.astimezone(_PRACTICE_TZ)
    year, month = local.year, local.month - months_back
    while month < 1:
        month += 12
        year -= 1
    return datetime(year, month, 1, tzinfo=_PRACTICE_TZ).astimezone(timezone.utc)


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
        ).where(*conditions)
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
        .where(ServiceAgreement.status != ServiceAgreementStatus.superseded)
        .order_by(ServiceAgreement.created_at.desc())
        .limit(200)
    ).all()

    signed_total = _sum_and_count(db, signed)
    priced_signed = signed_total["count"] - signed_total["unpriced"]

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
        "agreements": [
            {
                "agreement_id": str(a.id),
                "lead_id": str(a.lead_id) if a.lead_id else None,
                "client": _lead_title(lead),
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


class AmountPatch(BaseModel):
    amount_minor: int | None = Field(default=None, ge=0, le=10**13)


@router.patch("/agreements/{agreement_id}/amount")
def set_agreement_amount(
    agreement_id: uuid.UUID,
    payload: AmountPatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Сумма к учёту — поле бухгалтерии, а не документа.

    Меняется и у подписанного договора: текст, под которым стоит подпись,
    остаётся прежним, а вот учётная сумма могла быть не проставлена вовсе —
    у договоров, составленных до того, как она появилась.
    """
    item = db.get(ServiceAgreement, agreement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
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
