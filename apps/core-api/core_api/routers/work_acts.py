"""Акт выполненных работ по уже подписанному договору.

Отдельно от service_agreements.py: договор описывает условия и подписывается
обеими сторонами, акт — что по ним фактически сделано и сколько к оплате,
проще и без двустороннего подтверждения. «Оплачено» юрист отмечает сам:
самозанятый без ИП не может подключить эквайринг и проверять зачисления
банковским API — деньги в любом случае идёт переводом, а видит их только он.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.config import get_settings
from core_api.db import get_db
from core_api.lead_notifications import _post_telegram_message
from core_api.models import (
    ActorType,
    Scope,
    ServiceAgreement,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)

router = APIRouter(prefix="/api/v1/work-acts", tags=["work-acts"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _next_act_number() -> str:
    return f"AC-{_now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def _client_bot_token() -> str:
    settings = get_settings()
    return (
        getattr(settings, "lead_bot_token", None)
        or getattr(settings, "lead_notify_bot_token", None)
        or ""
    )


def _format_rub(amount_minor: int) -> str:
    rubles, kopecks = divmod(amount_minor, 100)
    whole = f"{rubles:,}".replace(",", " ")
    return f"{whole},{kopecks:02d} ₽" if kopecks else f"{whole} ₽"


def _get(db: Session, act_id: uuid.UUID, *, lock: bool = False) -> WorkAct:
    stmt = select(WorkAct).where(WorkAct.id == act_id)
    if lock:
        stmt = stmt.with_for_update()
    item = db.execute(stmt).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Act not found")
    return item


def _payload(item: WorkAct) -> dict:
    return {
        "id": str(item.id),
        "act_number": item.act_number,
        "agreement_id": str(item.agreement_id),
        "lead_id": str(item.lead_id) if item.lead_id else None,
        "status": item.status.value,
        "description_text": item.description_text,
        "amount_minor": item.amount_minor,
        "currency": item.currency,
        "created_at": _iso(item.created_at),
        "sent_at": _iso(item.sent_at),
        "claimed_paid_at": _iso(item.claimed_paid_at),
        "paid_at": _iso(item.paid_at),
        "paid_note": item.paid_note,
    }


def _audit(
    db: Session,
    identity: ApiKeyIdentity,
    item: WorkAct,
    action: str,
    details: dict | None = None,
) -> None:
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action=action,
        target_type="work_act",
        target_id=item.id,
        details=details or {},
    )


class ActCreate(BaseModel):
    agreement_id: uuid.UUID
    description_text: str = Field(min_length=2, max_length=4000)
    amount_minor: int = Field(ge=0, le=10**13)
    prepared_by_telegram_user_id: int | None = Field(default=None, gt=0)


@router.post("", status_code=201)
def create_act(
    payload: ActCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Заводит акт по подписанному договору — только по нему: выставлять
    счёт за работу, которую клиент ещё не принял, нечем обосновать."""
    agreement = db.get(ServiceAgreement, payload.agreement_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if agreement.status != ServiceAgreementStatus.signed:
        raise HTTPException(status_code=409, detail="Act can only be issued for a signed agreement")

    item = WorkAct(
        act_number=_next_act_number(),
        agreement_id=agreement.id,
        lead_id=agreement.lead_id,
        description_text=payload.description_text.strip(),
        amount_minor=payload.amount_minor,
        currency=agreement.currency,
        prepared_by_telegram_user_id=payload.prepared_by_telegram_user_id,
    )
    db.add(item)
    _audit(db, identity, item, "work_act.create")
    db.commit()
    db.refresh(item)
    return _payload(item)


@router.get("/by-agreement/{agreement_id}")
def list_by_agreement(
    agreement_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = identity
    rows = (
        db.execute(
            select(WorkAct)
            .where(WorkAct.agreement_id == agreement_id)
            .order_by(WorkAct.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_payload(row) for row in rows]


def _build_act_text(item: WorkAct, agreement: ServiceAgreement) -> str:
    settings = get_settings()
    lines = [
        f"Акт выполненных работ № {item.act_number}",
        f"К договору № {agreement.agreement_number}",
        "",
        item.description_text,
        "",
        f"К оплате: {_format_rub(item.amount_minor)}",
    ]
    details = []
    if settings.lawyer_payment_card_number:
        details.append(f"Карта: <code>{settings.lawyer_payment_card_number}</code>")
    if settings.lawyer_payment_sbp_phone:
        details.append(f"СБП (тел.): <code>{settings.lawyer_payment_sbp_phone}</code>")
    if details:
        # Реквизиты в <code> — Telegram копирует такой текст по тапу, без
        # выделения вручную.
        lines += ["", "Оплата:"] + details
    return "\n".join(lines)


def _act_markup(act_id: str) -> str:
    return json.dumps(
        {"inline_keyboard": [[{"text": "Я оплатил(а)", "callback_data": f"act_c:claim:{act_id}"}]]},
        ensure_ascii=False,
    )


@router.post("/{act_id}/send")
def send_act(
    act_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Отправляет акт клиенту и отмечает отправку.

    Единственное место доставки — тот же приём, что у deliver_agreement: и
    кнопка в боте, и рабочее место юриста вызывают эту, а не собирают текст
    каждый по-своему.
    """
    item = _get(db, act_id, lock=True)
    if item.status != WorkActStatus.draft:
        raise HTTPException(status_code=409, detail="Act is not a draft")
    agreement = db.get(ServiceAgreement, item.agreement_id)
    if agreement is None or not agreement.client_telegram_user_id:
        raise HTTPException(status_code=409, detail="Client has no Telegram")

    token = _client_bot_token()
    if not token:
        raise HTTPException(status_code=500, detail="Bot token is not configured")

    try:
        sent = _post_telegram_message(
            token,
            str(agreement.client_telegram_user_id),
            _build_act_text(item, agreement),
            reply_markup=_act_markup(str(item.id)),
            parse_mode="HTML",
        )
    except Exception as exc:  # noqa: BLE001 — причина уходит юристу, а не в трейс
        raise HTTPException(
            status_code=502, detail=f"Telegram delivery failed: {type(exc).__name__}"
        ) from exc

    item.status = WorkActStatus.sent
    item.sent_at = _now()
    item.sent_chat_id = agreement.client_telegram_user_id
    item.sent_message_id = sent.get("message_id")
    db.add(item)
    _audit(db, identity, item, "work_act.send")
    db.commit()
    db.refresh(item)
    return _payload(item)


class ClaimPaid(BaseModel):
    telegram_user_id: int = Field(gt=0)


@router.post("/{act_id}/claim-paid")
def claim_paid(
    act_id: uuid.UUID,
    payload: ClaimPaid,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Клиент нажал «Я оплатил(а)» — заявление, не подтверждение: реальную
    оплату видит только юрист, он и переводит статус в paid отдельно."""
    item = _get(db, act_id, lock=True)
    agreement = db.get(ServiceAgreement, item.agreement_id)
    if agreement is None or agreement.client_telegram_user_id != payload.telegram_user_id:
        # Тот же id акта не должен уходить в paid по чужому клику — даже
        # заявление о нём принимаем только от адресата.
        raise HTTPException(status_code=403, detail="Not the client of this act")
    if item.status not in (WorkActStatus.sent, WorkActStatus.claimed_paid):
        raise HTTPException(status_code=409, detail="Act is not awaiting payment")
    if item.status == WorkActStatus.sent:
        item.status = WorkActStatus.claimed_paid
        item.claimed_paid_at = _now()
        db.add(item)
        _audit(db, identity, item, "work_act.claim_paid")
        db.commit()
        db.refresh(item)
    return _payload(item)


class MarkPaid(BaseModel):
    paid_by_telegram_user_id: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)


@router.patch("/{act_id}/paid")
def mark_paid(
    act_id: uuid.UUID,
    payload: MarkPaid,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Юрист подтверждает получение денег — из sent (сразу, без клика
    клиента) или из claimed_paid (клиент уже заявил)."""
    item = _get(db, act_id, lock=True)
    if item.status not in (WorkActStatus.sent, WorkActStatus.claimed_paid):
        raise HTTPException(status_code=409, detail="Act is not awaiting payment")
    item.status = WorkActStatus.paid
    item.paid_at = _now()
    item.paid_by_telegram_user_id = payload.paid_by_telegram_user_id
    item.paid_note = payload.note.strip() if payload.note else None
    db.add(item)
    _audit(db, identity, item, "work_act.paid", {"note": item.paid_note} if item.paid_note else None)
    db.commit()
    db.refresh(item)
    return _payload(item)
