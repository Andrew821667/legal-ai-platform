"""Запись на платную консультацию — самый короткий путь от посетителя к деньгам.

Юрист открывает время. Клиент на сайте выбирает его, оставляет описание и
контакт — обращение создаётся тем же путём, что и любая заявка с сайта, а
время держится за ним CONSULTATION_HOLD_MINUTES. Клиент платит по QR
(реквизиты — те же, что у актов, payment_qr) и нажимает «Я оплатил»;
юрист видит поступление в банке и подтверждает одним нажатием.

Почему подтверждает юрист, а не банк: у самозанятого нет банковского API,
который видел бы поступления, а эквайринг (ЮKassa и подобные) требует
отдельного договора. Подтверждение устроено как один переход статуса —
вебхук эквайринга сможет делать его вместо юриста.

Статусы: free → held (клиент выбрал, оплачивает) → claimed (сообщил об
оплате) → confirmed (юрист увидел деньги). Неоплаченная бронь по истечении
времени сама возвращается в free. cancelled — время закрыл юрист.

«Оплатить сейчас, время согласуем» (решение владельца 01.10.2026): бронь без
времени — starts_at пусто, юрист назначает время после разговора (schedule).
Такая бронь при истечении или отмене не становится «свободным временем», а
закрывается (cancelled): времени, которое можно отдать другому, у неё нет.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from core_api.config import get_settings
from core_api.models import ConsultationSlot, Lead, LegalIntake

MOSCOW = ZoneInfo("Europe/Moscow")
BOOKED = ("held", "claimed", "confirmed")
MAX_DAYS_AHEAD = 60


class SlotUnavailable(Exception):
    """Время уже занято, прошло или слишком близко."""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def release_expired(db: Session, now: datetime) -> int:
    """Неоплаченные брони с истёкшим сроком — снова свободное время
    (брони без времени просто закрываются)."""
    expired = (ConsultationSlot.status == "held", ConsultationSlot.held_until < now)
    released = db.execute(
        update(ConsultationSlot)
        .where(*expired, ConsultationSlot.starts_at.is_not(None))
        .values(status="free", lead_id=None, intake_id=None, price_minor=None, code=None, access_token=None,
                held_until=None)
    ).rowcount
    closed = db.execute(
        update(ConsultationSlot)
        .where(*expired, ConsultationSlot.starts_at.is_(None))
        .values(status="cancelled", cancelled_at=now, access_token=None, held_until=None)
    ).rowcount
    return released + closed


def _earliest(now: datetime) -> datetime:
    return now + timedelta(hours=get_settings().consultation_min_notice_hours)


def free_slots(db: Session, now: datetime, days: int = 21) -> list[dict]:
    rows = db.scalars(
        select(ConsultationSlot)
        .where(ConsultationSlot.status == "free")
        .where(ConsultationSlot.starts_at >= _earliest(now))
        .where(ConsultationSlot.starts_at < now + timedelta(days=days))
        .order_by(ConsultationSlot.starts_at)
    )
    return [{"slot_id": str(row.id), "starts_at": row.starts_at.isoformat(), "duration_min": row.duration_min}
            for row in rows]


def hold(db: Session, slot_id: uuid.UUID, lead: Lead, intake: LegalIntake, now: datetime) -> ConsultationSlot:
    """Забронировать время за обращением. Строка блокируется: двое не займут одно время."""
    slot = db.execute(
        select(ConsultationSlot).where(ConsultationSlot.id == slot_id).with_for_update()
    ).scalar_one_or_none()
    if slot is None:
        raise SlotUnavailable
    if slot.status == "held" and slot.held_until is not None and slot.held_until < now:
        slot.status = "free"
    if slot.status != "free" or slot.starts_at < _earliest(now):
        raise SlotUnavailable
    settings = get_settings()
    slot.status = "held"
    slot.lead_id = lead.id
    slot.intake_id = intake.id
    slot.price_minor = settings.consultation_price_minor
    slot.code = f"K-{secrets.token_hex(3).upper()}"
    slot.access_token = secrets.token_urlsafe(24)
    slot.held_until = now + timedelta(minutes=settings.consultation_hold_minutes)
    slot.claimed_at = slot.confirmed_at = slot.cancelled_at = None
    slot.receipt_ref = slot.receipt_at = None
    return slot


def hold_unscheduled(db: Session, lead: Lead, intake: LegalIntake, now: datetime) -> ConsultationSlot:
    """Бронь без времени: клиент оплачивает сейчас, время юрист согласует с ним."""
    settings = get_settings()
    slot = ConsultationSlot(
        starts_at=None,
        duration_min=60,
        status="held",
        lead_id=lead.id,
        intake_id=intake.id,
        price_minor=settings.consultation_price_minor,
        code=f"K-{secrets.token_hex(3).upper()}",
        access_token=secrets.token_urlsafe(24),
        held_until=now + timedelta(minutes=settings.consultation_hold_minutes),
    )
    db.add(slot)
    db.flush()
    return slot


def schedule(db: Session, slot: ConsultationSlot, starts_at: datetime, now: datetime) -> None:
    """Юрист назначил согласованное время. Занятое другой записью — нельзя."""
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=MOSCOW)
    if starts_at <= now or starts_at > now + timedelta(days=MAX_DAYS_AHEAD):
        raise SlotUnavailable
    taken = db.scalar(
        select(func.count()).select_from(ConsultationSlot)
        .where(ConsultationSlot.starts_at == starts_at, ConsultationSlot.status != "cancelled",
               ConsultationSlot.id != slot.id)
    )
    if taken:
        raise SlotUnavailable
    slot.starts_at = starts_at


def local(value: datetime) -> datetime:
    return value.astimezone(MOSCOW)


def when_text(slot: ConsultationSlot) -> str:
    if slot.starts_at is None:
        return "время согласуем с вами"
    start = local(slot.starts_at)
    return f"{start:%d.%m.%Y} в {start:%H:%M} (МСК)"


def purpose(slot: ConsultationSlot) -> str:
    """Назначение платежа: по коду юрист находит перевод в выписке."""
    if slot.starts_at is None:
        return f"Консультация юриста, код {slot.code}. НДС не облагается"
    return f"Консультация {local(slot.starts_at):%d.%m.%Y %H:%M}, код {slot.code}. НДС не облагается"


def booking(slot: ConsultationSlot) -> dict:
    return {
        "slot_id": str(slot.id),
        # None — время согласуем с клиентом (бронь без времени).
        "starts_at": slot.starts_at.isoformat() if slot.starts_at else None,
        "duration_min": slot.duration_min,
        "status": slot.status,
        "price_minor": slot.price_minor,
        "code": slot.code,
        "access_token": slot.access_token,
        "held_until": slot.held_until.isoformat() if slot.held_until else None,
        "claimed_at": slot.claimed_at.isoformat() if slot.claimed_at else None,
        "confirmed_at": slot.confirmed_at.isoformat() if slot.confirmed_at else None,
    }


def by_token(db: Session, token: str, *, lock: bool = False) -> ConsultationSlot | None:
    stmt = select(ConsultationSlot).where(ConsultationSlot.access_token == token)
    if lock:
        stmt = stmt.with_for_update()
    slot = db.execute(stmt).scalar_one_or_none()
    return slot if slot is not None and slot.status in BOOKED else None


def release(slot: ConsultationSlot) -> None:
    """Бронь снята — время снова свободно (если оно ещё впереди).
    Бронь без времени просто закрывается: отдавать некого время."""
    if slot.starts_at is None:
        slot.status = "cancelled"
        slot.cancelled_at = now_utc()
        slot.access_token = None
        slot.held_until = None
        return
    slot.status = "free"
    slot.lead_id = slot.intake_id = None
    slot.price_minor = None
    slot.code = slot.access_token = None
    slot.held_until = slot.claimed_at = slot.confirmed_at = None
    slot.receipt_ref = slot.receipt_at = None


def income_since(db: Session, since: datetime) -> int:
    """Оплаченные консультации — доход самозанятого (лимит НПД)."""
    total = db.scalar(
        select(func.coalesce(func.sum(ConsultationSlot.price_minor), 0))
        .where(ConsultationSlot.status == "confirmed")
        .where(ConsultationSlot.confirmed_at >= since)
    )
    return int(total or 0)


def for_intake(db: Session, intake_id: uuid.UUID) -> ConsultationSlot | None:
    return db.scalar(
        select(ConsultationSlot)
        .where(ConsultationSlot.intake_id == intake_id, ConsultationSlot.status.in_(BOOKED))
        .order_by(ConsultationSlot.starts_at.desc())
        .limit(1)
    )

