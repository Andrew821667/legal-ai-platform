"""«Сегодня»: что стоит без движения из-за юриста.

Список всех клиентов такого ответа не даёт — по нему приходится вспоминать,
кому что обещал. Поэтому экран показывает не всё подряд, а застрявшее:
неотправленный черновик договора, вопрос клиента без ответа, обращение, по
которому никто не связался.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api import telegram_delivery
from core_api.config import get_settings
from core_api.db import get_db
from core_api.staff import is_staff
from core_api.models import (
    ClientReview,
    Lead,
    LegalIntake,
    LegalIntakeStatus,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
    ServiceAgreementStatus,
    TelegramDelivery,
    WorkAct,
    WorkActStatus,
)
from core_api.routers.lawyer_workspace.common import (
    _AWAITING_CLIENT_DAYS,
    _EXPIRING_SOON_DAYS,
    _DEADLINE_SOON_DAYS,
    _lead_title,
    _iso,
    _days_since,
    _days_until,
)
from core_api.routers.lawyer_workspace.money import (
    _RECEIPT_LOOKBACK_DAYS,
    _ACT_OPEN,
    _counted_acts,
    _overdue,
)

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


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

    # Отзыв с согласием на публикацию ждёт решения юриста.
    reviews_pending = db.execute(
        select(ClientReview, WorkAct, Lead)
        .join(WorkAct, WorkAct.id == ClientReview.act_id)
        .outerjoin(Lead, Lead.id == ClientReview.lead_id)
        .where(ClientReview.status == "pending")
        .where(ClientReview.publish_consent.is_(True))
        .where(ClientReview.text.is_not(None))
        .order_by(ClientReview.updated_at)
    ).all()

    # Оплачено, а чек в «Мой налог» не записан. Самозанятый обязан выдать
    # чек при расчёте; старые оплаты не тянем — только за два месяца.
    receipt_missing = db.execute(
        _counted_acts()
        .where(WorkAct.status == WorkActStatus.paid)
        .where(WorkAct.receipt_at.is_(None))
        .where(WorkAct.paid_at >= now - timedelta(days=_RECEIPT_LOOKBACK_DAYS))
        .order_by(WorkAct.paid_at)
    ).all()

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
                "key": "review_moderation",
                "title": "Отзыв ждёт решения",
                "hint": "Клиент разрешил публикацию. На сайте будет только имя, оценка и текст.",
                "items": [
                    {
                        "review_id": str(r.id),
                        "lead_id": str(r.lead_id) if r.lead_id else None,
                        "client": _lead_title(lead),
                        "is_test": is_staff(r.telegram_user_id),
                        "act_number": act.act_number,
                        "score": r.score,
                        "review_text": (r.text or "")[:600],
                        "days_waiting": _days_since(r.updated_at),
                    }
                    for r, act, lead in reviews_pending
                ],
            },
            {
                "key": "receipt_missing",
                "title": "Чек не выдан",
                "hint": "Оплата отмечена, а чека из «Мой налог» нет — выдайте и отправьте клиенту.",
                "items": [
                    {
                        "act_id": str(a.id),
                        "lead_id": str(a.lead_id) if a.lead_id else None,
                        "client": _lead_title(lead),
                        "is_test": is_staff(lead.telegram_user_id if lead else None),
                        "act_number": a.act_number,
                        "amount_minor": a.amount_minor,
                        "paid_at": _iso(a.paid_at),
                        "days_waiting": _days_since(a.paid_at),
                    }
                    for a, lead in receipt_missing
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
