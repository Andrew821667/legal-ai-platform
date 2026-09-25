"""Отзывы клиентов: просьба после оплаты, приём, публикация.

Отзывы — главный довод для нового клиента юриста, а собирать их было нечем.
Через сутки после оплаты акта бот один раз просит оценить работу кнопками
1–5 ⭐, потом — пару слов и разрешение опубликовать. На сайт попадает только
то, на что клиент дал согласие и что одобрил юрист; имя — только первое.

Просьбу отправляет такт ядра (см. telegram_ops), только днём по Москве и
только при живой связи с Telegram. Отправка не повторяется: вторая просьба
об отзыве — навязчиво.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api import telegram_delivery
from core_api.audit import write_audit
from core_api.client_notices import queue_notice
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.models import ActorType, ClientReview, Lead, ServiceAgreement, WorkAct, WorkActStatus
from core_api.staff import real_client

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))
DAY_START_HOUR = 10
DAY_END_HOUR = 20
# Сутки после оплаты: сразу — похоже на автоответчик, позже месяца — клиент уже забыл.
ASK_AFTER = timedelta(hours=24)
ASK_WITHIN = timedelta(days=30)
_BATCH = 20
ACTOR = "client_reviews"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def request_markup(act_id: str) -> str:
    """Оценка одной кнопкой; callback_data — договорённость с ботом (act_c:rv)."""
    row = [{"text": f"{n} ⭐", "callback_data": f"act_c:rv:{act_id}:{n}"} for n in range(1, 6)]
    return json.dumps({"inline_keyboard": [row]}, ensure_ascii=False)


def request_text(act_number: str) -> str:
    return (
        f"Работа по акту № {act_number} завершена — спасибо, что обратились.\n\n"
        "Оцените, пожалуйста, работу юриста — это займёт секунду:"
    )


def process_due(now: datetime | None = None, transport: telegram_delivery.Transport | None = None) -> dict:
    if not get_settings().review_requests_enabled:
        return {"skipped": "disabled"}
    now = now or _now()
    if not DAY_START_HOUR <= now.astimezone(MSK).hour < DAY_END_HOUR:
        return {"skipped": "night"}
    token = telegram_delivery._client_token()
    if not token:
        return {"skipped": "no_token"}

    outgoing: list[dict] = []
    db = SessionLocal()
    try:
        rows = db.execute(
            select(WorkAct, ServiceAgreement.client_telegram_user_id)
            .join(ServiceAgreement, ServiceAgreement.id == WorkAct.agreement_id)
            .outerjoin(Lead, Lead.id == WorkAct.lead_id)
            .where(Lead.archived_at.is_(None))
            .where(real_client(Lead.telegram_user_id))
            .where(ServiceAgreement.client_telegram_user_id.is_not(None))
            .where(WorkAct.status == WorkActStatus.paid)
            .where(WorkAct.cancelled_at.is_(None))
            .where(WorkAct.review_requested_at.is_(None))
            .where(WorkAct.paid_at <= now - ASK_AFTER)
            .where(WorkAct.paid_at >= now - ASK_WITHIN)
            .order_by(WorkAct.paid_at)
            .limit(_BATCH)
            .with_for_update(of=WorkAct, skip_locked=True)
        ).all()
        for act, chat_id in rows:
            act.review_requested_at = now
            outgoing.append(
                {"act_id": act.id, "act_number": act.act_number, "lead_id": act.lead_id,
                 "agreement_id": act.agreement_id, "chat_id": chat_id}
            )
        db.commit()
    finally:
        db.close()

    outcome = {"sent": 0, "failed": 0}
    for message in outgoing:
        try:
            telegram_delivery.send(
                kind="review_request",
                token=token,
                chat_id=message["chat_id"],
                text=request_text(message["act_number"]),
                reply_markup=request_markup(str(message["act_id"])),
                lead_id=message["lead_id"],
                agreement_id=message["agreement_id"],
                act_id=message["act_id"],
                transport=transport,
            )
        except Exception as exc:  # noqa: BLE001 — исход уже в журнале отправок
            logger.warning("review request failed: act=%s %s", message["act_id"], telegram_delivery.safe_error(exc))
            outcome["failed"] += 1
        else:
            outcome["sent"] += 1
    return outcome


def record(
    db: Session,
    act: WorkAct,
    *,
    telegram_user_id: int,
    actor: str,
    score: int | None = None,
    text: str | None = None,
    publish_consent: bool | None = None,
) -> ClientReview:
    """Оценка, текст и согласие приходят по отдельности — по кнопкам и сообщению."""
    review = db.scalar(select(ClientReview).where(ClientReview.act_id == act.id).with_for_update())
    if review is None:
        review = ClientReview(act_id=act.id, lead_id=act.lead_id, telegram_user_id=telegram_user_id)
        db.add(review)
        db.flush()
    lead = db.get(Lead, act.lead_id) if act.lead_id else None
    who = (lead.name if lead and lead.name else "Клиент").split()[0]
    if score is not None and score != review.score:
        review.score = score
        queue_notice(
            db,
            f"review_score:{review.id}:{score}",
            f"Оценка работы по акту № {act.act_number} от {who}: {'⭐' * score} ({score} из 5).",
        )
    if text is not None:
        cleaned = " ".join(text.split())
        if cleaned != (review.text or ""):
            review.text = cleaned
            # Новый текст — новое решение юриста о публикации.
            review.status = "pending"
            review.moderated_at = None
            digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:12]
            queue_notice(db, f"review_text:{review.id}:{digest}", f"Отзыв по акту № {act.act_number} от {who}:\n«{cleaned[:1500]}»")
    if publish_consent is not None:
        review.publish_consent = publish_consent
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=actor,
        action="client_review.record",
        target_type="client_review",
        target_id=review.id,
        details={
            "score": score,
            "text": text is not None,
            "publish_consent": publish_consent,
        },
    )
    return review


def payload(review: ClientReview | None) -> dict | None:
    if review is None:
        return None
    return {
        "review_id": str(review.id),
        "score": review.score,
        "text": review.text,
        "publish_consent": review.publish_consent,
        "status": review.status,
    }


def public(db: Session, limit: int = 20) -> list[dict]:
    """Для сайта: одобренные отзывы с согласием клиента; имя — только первое."""
    rows = db.execute(
        select(ClientReview, Lead)
        .outerjoin(Lead, Lead.id == ClientReview.lead_id)
        .where(ClientReview.status == "approved")
        .where(ClientReview.publish_consent.is_(True))
        .where(ClientReview.text.is_not(None))
        .where(real_client(ClientReview.telegram_user_id))
        .order_by(ClientReview.moderated_at.desc().nulls_last())
        .limit(limit)
    ).all()
    return [
        {
            "name": ((lead.name if lead and lead.name else "").split() or ["Клиент"])[0],
            "score": review.score,
            "text": review.text,
            "date": review.created_at.astimezone(MSK).date().isoformat() if review.created_at else None,
        }
        for review, lead in rows
    ]
