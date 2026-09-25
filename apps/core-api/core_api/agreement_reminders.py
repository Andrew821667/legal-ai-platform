"""Напоминание клиенту о неподписанном договоре — само, без юриста.

Договор уходил клиенту, и если тот отвлёкся, предложение тихо сгорало через
неделю: напомнить мог только юрист, вспомнив об этом сам. Теперь ядро
напоминает само, но сдержанно:

- первый раз — через AGREEMENT_REMIND_AFTER_DAYS дней после отправки;
- второй и последний — в последние сутки перед окончанием предложения, с датой;
- только днём по Москве: напоминание в полночь раздражает больше, чем помогает;
- не напоминает, если клиент задал вопрос и ждёт ответа юриста: ход не за ним;
- не напоминает клиенту из архива.

Запускается из того же такта, что проверка связи с Telegram (см. telegram_ops),
и только когда связь есть. Отправка не повторяется: повтор мог бы прийти уже
после подписания. Неудача видна юристу в «Не доставлено».
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from core_api import telegram_delivery
from core_api.audit import write_audit
from core_api.client_proposal import build_proposal_markup, build_reminder_text
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.models import (
    ActorType,
    Lead,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
    ServiceAgreementStatus,
)

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))
# Часы по Москве, в которые можно напоминать: с 10:00 до 20:00.
DAY_START_HOUR = 10
DAY_END_HOUR = 20
# Последнее напоминание — когда до окончания предложения меньше суток.
LAST_CALL = timedelta(hours=24)
_MIN_GAP = timedelta(hours=24)
_BATCH = 20
ACTOR = "agreement_reminders"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_daytime(now: datetime) -> bool:
    return DAY_START_HOUR <= now.astimezone(MSK).hour < DAY_END_HOUR


def _awaits_lawyer():
    """Последнее сообщение по договору — от клиента: он ждёт ответа юриста."""
    last_role = (
        select(ServiceAgreementMessage.role)
        .where(ServiceAgreementMessage.agreement_id == ServiceAgreement.id)
        .order_by(ServiceAgreementMessage.created_at.desc())
        .limit(1)
        .correlate(ServiceAgreement)
        .scalar_subquery()
    )
    return and_(last_role.is_not(None), last_role == ServiceAgreementMessageRole.client)


def _due(db: Session, now: datetime, after: timedelta) -> list[ServiceAgreement]:
    first = and_(ServiceAgreement.reminders_sent == 0, ServiceAgreement.sent_at <= now - after)
    last_call = and_(
        ServiceAgreement.reminders_sent == 1,
        ServiceAgreement.expires_at.is_not(None),
        ServiceAgreement.expires_at <= now + LAST_CALL,
        or_(
            ServiceAgreement.last_reminded_at.is_(None),
            ServiceAgreement.last_reminded_at <= now - _MIN_GAP,
        ),
    )
    stmt = (
        select(ServiceAgreement)
        .outerjoin(Lead, Lead.id == ServiceAgreement.lead_id)
        .where(Lead.archived_at.is_(None))
        .where(ServiceAgreement.status.in_([ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed]))
        .where(ServiceAgreement.client_telegram_user_id.is_not(None))
        .where(ServiceAgreement.sent_at.is_not(None))
        .where(or_(ServiceAgreement.expires_at.is_(None), ServiceAgreement.expires_at > now))
        .where(or_(first, last_call))
        .where(~_awaits_lawyer())
        .order_by(ServiceAgreement.sent_at)
        .limit(_BATCH)
        .with_for_update(of=ServiceAgreement, skip_locked=True)
    )
    return list(db.scalars(stmt).all())


def process_due(now: datetime | None = None, transport: telegram_delivery.Transport | None = None) -> dict:
    """Напоминает по всем договорам, чей срок подошёл.

    Сначала отмечает напоминания и отпускает блокировку, потом отправляет:
    держать строки заблокированными, пока идёт запрос в Telegram, незачем, а
    отметка до отправки не даст второму такту напомнить дважды.
    """
    settings = get_settings()
    after_days = settings.agreement_remind_after_days
    if after_days <= 0:
        return {"skipped": "disabled"}
    now = now or _now()
    if not is_daytime(now):
        return {"skipped": "night"}
    token = telegram_delivery._client_token()
    if not token:
        return {"skipped": "no_token"}

    # Текст — из того же словаря, что и исходное предложение: иначе у
    # напоминания и договора разошлись бы номер, сумма или вид документа.
    from core_api.routers.service_agreements import _is_supplement, _payload

    outgoing: list[dict] = []
    db = SessionLocal()
    try:
        for item in _due(db, now, timedelta(days=after_days)):
            # Предложение сгорает в ближайшие сутки — о сроке сказать важнее всего.
            expires_soon = item.expires_at is not None and item.expires_at <= now + LAST_CALL
            expires_on = item.expires_at.astimezone(MSK).strftime("%d.%m") if expires_soon else None
            item.reminders_sent += 1
            item.last_reminded_at = now
            write_audit(
                db,
                actor_type=ActorType.system,
                actor_id=ACTOR,
                action="service_agreement.remind",
                target_type="service_agreement",
                target_id=item.id,
                details={"reminder": item.reminders_sent},
            )
            outgoing.append(
                {
                    "agreement_id": item.id,
                    "lead_id": item.lead_id,
                    "chat_id": item.client_telegram_user_id,
                    "text": build_reminder_text(_payload(item), expires_on=expires_on),
                    "markup": build_proposal_markup(str(item.id), supplement=_is_supplement(item)),
                }
            )
        db.commit()
    finally:
        db.close()

    outcome = {"sent": 0, "failed": 0}
    for message in outgoing:
        try:
            telegram_delivery.send(
                kind="agreement_reminder",
                token=token,
                chat_id=message["chat_id"],
                text=message["text"],
                reply_markup=message["markup"],
                lead_id=message["lead_id"],
                agreement_id=message["agreement_id"],
                transport=transport,
            )
        except Exception as exc:  # noqa: BLE001 — исход уже в журнале отправок
            logger.warning(
                "agreement reminder failed: agreement=%s %s",
                message["agreement_id"],
                telegram_delivery.safe_error(exc),
            )
            outcome["failed"] += 1
        else:
            outcome["sent"] += 1
    return outcome

