"""Деньги практики: итоги по договорам и актам, воронка, сумма к учёту."""

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
from core_api import npd_limit, practice_funnel
from core_api.config import get_settings
from core_api.db import get_db
from core_api.staff import is_staff, real_client, staff_telegram_ids
from core_api.models import (
    ActorType,
    Lead,
    Scope,
    ServiceAgreement,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)
from core_api.routers.lawyer_workspace.common import (
    _lead_title,
    _iso,
    _days_since,
)

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


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
# Сколько дней назад оплаченный акт ещё ждёт чека в «Сегодня».
_RECEIPT_LOOKBACK_DAYS = 60
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
        # Доход за год против лимита самозанятого.
        "npd": npd_limit.summary(db, now),
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
