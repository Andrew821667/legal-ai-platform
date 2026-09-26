"""Список клиентов и история событий клиента."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api import case_stage
from core_api.db import get_db
from core_api.staff import is_staff
from core_api.models import (
    AuditLog,
    Lead,
    LegalIntake,
    LegalIntakeStatus,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
)
from core_api.routers.lawyer_workspace.common import (
    _lead_title,
    _iso,
    _worked_without_agreement,
)
from core_api.routers.lawyer_workspace.money import (
    _MONEY_STATUSES,
)

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


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
