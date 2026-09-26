"""Запись на платную консультацию (см. core_api.consultations).

Две стороны. Сайт (ключ бота) — свободное время и бронь клиента по её ключу:
страница брони, QR, «Я оплатил», отмена. Юрист (ключ администратора) —
открыть и закрыть время, увидеть записи, подтвердить оплату, снять бронь,
отметить чек. Бронь создаётся не здесь, а вместе с обращением
(POST /api/v1/legal-intakes с consultation_slot_id).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core_api import consultations, npd_limit, payment_qr, telegram_delivery
from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.client_notices import queue_notice
from core_api.db import get_db
from core_api.models import ActorType, ConsultationSlot, Lead, Scope

logger = logging.getLogger(__name__)

public = APIRouter(prefix="/api/v1/consultations", tags=["consultations"])
lawyer = APIRouter(prefix="/api/v1/lawyer/consultations", tags=["lawyer-workspace"])

Token = Path(pattern=r"^[A-Za-z0-9_-]{20,64}$")


def _rub(minor: int | None) -> str:
    return f"{(minor or 0) // 100:,}".replace(",", " ") + " ₽"


def _audit(db: Session, identity: ApiKeyIdentity, slot: ConsultationSlot, action: str) -> None:
    write_audit(db, actor_type=ActorType.api_key, actor_id=identity.name, action=action,
                target_type="consultation_slot", target_id=slot.id, details={"status": slot.status})


def _booked(db: Session, token: str, *, lock: bool = False) -> ConsultationSlot:
    consultations.release_expired(db, consultations.now_utc())
    slot = consultations.by_token(db, token, lock=lock)
    if slot is None:
        # Бронь сгорела или её не было — одинаково: «не найдена».
        raise HTTPException(status_code=404, detail="Booking not found")
    return slot


# ---- Сайт ------------------------------------------------------------------


@public.get("/slots")
def slots(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    _ = identity
    now = consultations.now_utc()
    consultations.release_expired(db, now)
    db.commit()
    settings = consultations.get_settings()
    return {
        "price_minor": settings.consultation_price_minor,
        "hold_minutes": settings.consultation_hold_minutes,
        "slots": consultations.free_slots(db, now),
    }


@public.get("/bookings/{token}")
def booking(
    token: str = Token,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    _ = identity
    slot = _booked(db, token)
    db.commit()
    return {**consultations.booking(slot), "payment": payment_qr.requisites() is not None}


@public.get("/bookings/{token}/payment-qr", response_model=None)
def booking_qr(
    token: str = Token,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> Response:
    _ = identity
    slot = _booked(db, token)
    db.commit()
    if slot.status == "confirmed":
        # Оплата уже подтверждена: QR привёл бы к лишнему переводу.
        raise HTTPException(status_code=409, detail="Booking is already paid")
    data = payment_qr.payload(slot.price_minor or 0, consultations.purpose(slot))
    if data is None:
        raise HTTPException(status_code=404, detail="Payment QR is not configured")
    return Response(content=payment_qr.png(data), media_type="image/png",
                    headers={"Cache-Control": "no-store", "Content-Disposition": 'inline; filename="qr.png"'})


@public.post("/bookings/{token}/claim")
def claim(
    token: str = Token,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Клиент говорит «оплатил»: время держится до решения юриста, юрист — сверить."""
    slot = _booked(db, token, lock=True)
    if slot.status == "held":
        slot.status = "claimed"
        slot.claimed_at = consultations.now_utc()
        slot.held_until = None
        _audit(db, identity, slot, "consultation.claim")
        lead = db.get(Lead, slot.lead_id) if slot.lead_id else None
        queue_notice(
            db,
            f"consultation-claim:{slot.id}:{slot.code}",
            f"Консультация {consultations.when_text(slot)}: клиент {lead.name if lead and lead.name else ''} "
            f"сообщил об оплате {_rub(slot.price_minor)}, код {slot.code}. Сверьте поступление и подтвердите "
            "в рабочем месте («Задачи»).",
        )
    db.commit()
    return consultations.booking(slot)


@public.post("/bookings/{token}/cancel")
def client_cancel(
    token: str = Token,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Клиент передумал до оплаты. После «оплатил» — только через юриста: деньги."""
    slot = _booked(db, token, lock=True)
    if slot.status != "held":
        raise HTTPException(status_code=409, detail="Paid booking is cancelled by the lawyer")
    _audit(db, identity, slot, "consultation.client_cancel")
    consultations.release(slot)
    db.commit()
    return {"cancelled": True}


# ---- Юрист -----------------------------------------------------------------


class SlotsIn(BaseModel):
    starts_at: list[datetime] = Field(min_length=1, max_length=60)
    duration_min: int = Field(default=60, ge=15, le=240)


class ReceiptIn(BaseModel):
    ref: str | None = Field(default=None, max_length=500)


def _lawyer_slot(db: Session, slot_id: uuid.UUID) -> ConsultationSlot:
    slot = db.execute(select(ConsultationSlot).where(ConsultationSlot.id == slot_id).with_for_update()).scalar_one_or_none()
    if slot is None:
        raise HTTPException(status_code=404, detail="Consultation slot not found")
    return slot


def _row(slot: ConsultationSlot, lead: Lead | None) -> dict:
    return {
        **consultations.booking(slot),
        "lead_id": str(slot.lead_id) if slot.lead_id else None,
        "intake_id": str(slot.intake_id) if slot.intake_id else None,
        "client": (lead.name or lead.contact) if lead else None,
        "receipt_at": slot.receipt_at.isoformat() if slot.receipt_at else None,
        "receipt_ref": slot.receipt_ref,
    }


@lawyer.get("")
def lawyer_list(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Время на ближайшие недели и записи; прошедшее — за неделю, чтобы отметить чек."""
    _ = identity
    now = consultations.now_utc()
    consultations.release_expired(db, now)
    db.commit()
    rows = db.execute(
        select(ConsultationSlot, Lead)
        .outerjoin(Lead, Lead.id == ConsultationSlot.lead_id)
        .where(ConsultationSlot.status != "cancelled")
        .where(ConsultationSlot.starts_at >= now - timedelta(days=7))
        .order_by(ConsultationSlot.starts_at)
        .limit(200)
    ).all()
    return {
        "price_minor": consultations.get_settings().consultation_price_minor,
        "slots": [_row(slot, lead) for slot, lead in rows],
    }


@lawyer.post("/slots")
def open_slots(
    body: SlotsIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Открыть время. Прошедшее и уже открытое пропускается, а не ломает весь список."""
    now = consultations.now_utc()
    existing = set(db.scalars(
        select(ConsultationSlot.starts_at).where(ConsultationSlot.status != "cancelled")
        .where(ConsultationSlot.starts_at.in_(body.starts_at))
    ))
    created, skipped = [], 0
    for starts_at in sorted(set(body.starts_at)):
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=consultations.MOSCOW)
        if starts_at <= now or starts_at > now + timedelta(days=consultations.MAX_DAYS_AHEAD) or starts_at in existing:
            skipped += 1
            continue
        slot = ConsultationSlot(starts_at=starts_at, duration_min=body.duration_min, status="free")
        db.add(slot)
        created.append(slot)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Consultation slot already exists") from exc
    write_audit(db, actor_type=ActorType.api_key, actor_id=identity.name, action="consultation.open_slots",
                target_type="consultation_slot", target_id=None, details={"created": len(created), "skipped": skipped})
    db.commit()
    return {"created": [consultations.booking(slot) for slot in created], "skipped": skipped}


@lawyer.delete("/slots/{slot_id}")
def close_slot(
    slot_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Закрыть свободное время. Занятое сначала освобождают — там клиент."""
    slot = _lawyer_slot(db, slot_id)
    consultations.release_expired(db, consultations.now_utc())
    if slot.status != "free":
        raise HTTPException(status_code=409, detail="Consultation slot is booked")
    slot.status = "cancelled"
    slot.cancelled_at = consultations.now_utc()
    _audit(db, identity, slot, "consultation.close_slot")
    db.commit()
    return {"slot_id": str(slot.id), "closed": True}


@lawyer.post("/{slot_id}/confirm")
def confirm(
    slot_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Юрист увидел деньги в банке: запись подтверждена, клиенту — сообщение."""
    slot = _lawyer_slot(db, slot_id)
    if slot.status not in ("held", "claimed"):
        raise HTTPException(status_code=409, detail="Consultation is not awaiting payment")
    now = consultations.now_utc()
    slot.status = "confirmed"
    slot.confirmed_at = now
    slot.held_until = None
    _audit(db, identity, slot, "consultation.confirm")
    npd_limit.notify_if_crossed(db, now)
    db.commit()
    lead = db.get(Lead, slot.lead_id) if slot.lead_id else None
    delivered = "none"
    if lead is not None and lead.telegram_user_id:
        token = telegram_delivery._client_token()
        if token:
            try:
                telegram_delivery.send(
                    kind="consultation",
                    token=token,
                    chat_id=lead.telegram_user_id,
                    text=(f"Оплата получена — консультация подтверждена: {consultations.when_text(slot)}, "
                          f"до {slot.duration_min} минут. Юрист свяжется с вами перед началом."),
                    retryable=True,
                    lead_id=lead.id,
                )
                delivered = "telegram"
            except Exception as exc:  # noqa: BLE001 — исход в журнале отправок, повторит фон
                logger.warning("consultation notice failed: %s", telegram_delivery.safe_error(exc))
                delivered = "queued"
    return {**_row(slot, lead), "client_notified": delivered}


@lawyer.post("/{slot_id}/release")
def release_booking(
    slot_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Снять бронь: время снова свободно. Если оплата была — вернуть её юрист решает сам."""
    slot = _lawyer_slot(db, slot_id)
    if slot.status not in consultations.BOOKED:
        raise HTTPException(status_code=409, detail="Consultation slot is not booked")
    was = slot.status
    _audit(db, identity, slot, "consultation.release")
    consultations.release(slot)
    db.commit()
    return {"slot_id": str(slot.id), "released": True, "was": was}


@lawyer.post("/{slot_id}/receipt")
def receipt(
    slot_id: uuid.UUID,
    body: ReceiptIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Чек «Мой налог» за оплаченную консультацию — самозанятый обязан его выдать."""
    slot = _lawyer_slot(db, slot_id)
    if slot.status != "confirmed":
        raise HTTPException(status_code=409, detail="Receipt is recorded for a paid consultation")
    slot.receipt_ref = (body.ref or "").strip() or slot.receipt_ref
    slot.receipt_at = slot.receipt_at or consultations.now_utc()
    _audit(db, identity, slot, "consultation.receipt")
    db.commit()
    return _row(slot, db.get(Lead, slot.lead_id) if slot.lead_id else None)
