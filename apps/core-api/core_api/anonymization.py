"""Обезличивание персональных данных по сроку хранения (152-ФЗ).

Политика конфиденциальности обещает: потенциальные клиенты — «не более 3
лет», по истечении срока данные «уничтожаются или обезличиваются». На деле
всё хранилось бессрочно. Здесь это правило исполняется само, из такта ядра.

Кого: клиентов без договора, актов и заданий на проверку договора — у
клиентов с договором свой срок (действие договора + 5 лет), и его отсчёт —
отдельная задача. Когда:
- архивный — через ARCHIVE_ANONYMIZE_AFTER_DAYS (год) после архивации;
- любой — не позже PROSPECT_RETENTION_DAYS (3 года) с последней активности.

Что: имя, контакты, описания обращений, ответы на вопросы, ссылки на
присланные файлы, тексты сообщений клиенту, данные событий и заказов,
учётная запись входа, если других дел у неё нет. Запись клиента остаётся
(источник, даты, статусы) — на ней держатся воронка и итоги.

Подписанный NDA и согласие на обработку — доказательства: их данные о
подписанте живут три года с подписания (исковая давность) и обезличиваются
отдельным проходом. Хеш, версия и дата подписания остаются — факт подписи
подтверждается и после.

Необратимо, поэтому: только по сроку, пачками, с журналом аудита без
персональных данных и сообщением владельцу.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, and_, delete, exists, func, literal, or_, select, update
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.client_notices import queue_notice
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.models import (
    ActorType,
    ClientAccount,
    ContractJob,
    Event,
    IntakeClarification,
    IntakeDocument,
    Lead,
    LegalIntake,
    NdaPersonalDataConsent,
    NdaSignature,
    ServiceAgreement,
    SpecialConsultationOrder,
    TelegramDelivery,
    WorkAct,
)

logger = logging.getLogger(__name__)

PLACEHOLDER = "обезличено"
ANON_NAME = "Обезличенный клиент"
BATCH = 20


def _without_work():
    """Нет договора, акта и задания на проверку договора."""
    return and_(
        ~exists().where(ServiceAgreement.lead_id == Lead.id),
        ~exists().where(WorkAct.lead_id == Lead.id),
        ~exists().where(ContractJob.lead_id == Lead.id),
    )


def _last_activity():
    return func.greatest(
        Lead.created_at,
        func.coalesce(Lead.last_activity_at, Lead.created_at),
        func.coalesce(Lead.last_message_at, Lead.created_at),
    )


def due_leads(db: Session, now: datetime, limit: int = BATCH) -> list[uuid.UUID]:
    settings = get_settings()
    archived_before = now - timedelta(days=settings.archive_anonymize_after_days)
    inactive_before = now - timedelta(days=settings.prospect_retention_days)
    return list(
        db.scalars(
            select(Lead.id)
            .where(Lead.anonymized_at.is_(None))
            .where(_without_work())
            .where(
                or_(
                    and_(Lead.archived_at.is_not(None), Lead.archived_at < archived_before),
                    _last_activity() < inactive_before,
                )
            )
            .order_by(Lead.created_at)
            .limit(limit)
        )
    )


def has_work(db: Session, lead_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(select(Lead.id).where(Lead.id == lead_id).where(~_without_work()))
    )


def planned_date(db: Session, lead: Lead) -> datetime | None:
    """Когда архивный клиент будет обезличен — для экрана «Архив»."""
    settings = get_settings()
    if not settings.anonymize_enabled or lead.archived_at is None or lead.anonymized_at is not None:
        return None
    if has_work(db, lead.id):
        return None
    return lead.archived_at + timedelta(days=settings.archive_anonymize_after_days)


def _emails(lead: Lead) -> set[str]:
    found = set()
    for value in (lead.email, lead.contact):
        value = (value or "").strip().lower()
        if "@" in value:
            found.add(value)
    return found


def anonymize_lead(db: Session, lead: Lead, now: datetime) -> dict:
    """Обезличить одного клиента. Возвращает счётчики — без персональных данных."""
    emails = _emails(lead)
    counts = {"intakes": 0, "clarifications": 0, "documents": 0, "deliveries": 0, "events": 0, "accounts": 0}
    intake_ids = list(db.scalars(select(LegalIntake.id).where(LegalIntake.lead_id == lead.id)))

    if intake_ids:
        counts["intakes"] = db.execute(
            update(LegalIntake)
            .where(LegalIntake.id.in_(intake_ids))
            .values(description=f"[{PLACEHOLDER}]", deadline=None, region=None, internal_note=None)
        ).rowcount
        counts["clarifications"] = db.execute(
            delete(IntakeClarification).where(IntakeClarification.intake_id.in_(intake_ids))
        ).rowcount
        # Ссылки на файлы в Telegram: сами файлы остаются в чате юриста.
        counts["documents"] = db.execute(
            delete(IntakeDocument).where(IntakeDocument.intake_id.in_(intake_ids))
        ).rowcount

    counts["deliveries"] = db.execute(
        update(TelegramDelivery)
        .where(TelegramDelivery.lead_id == lead.id)
        .values(text=f"[{PLACEHOLDER}]", chat_id=PLACEHOLDER, reply_markup=None, retryable=False,
                next_attempt_at=None)
    ).rowcount
    counts["events"] = db.execute(update(Event).where(Event.lead_id == lead.id).values(payload={})).rowcount
    db.execute(
        update(SpecialConsultationOrder)
        .where(SpecialConsultationOrder.lead_id == lead.id)
        .values(telegram_user_id=None, customer_name=None, customer_contact=None, customer_email=None,
                customer_phone=None, customer_company=None, request_note=None, internal_note=None, context={})
    )

    lead.name = ANON_NAME
    lead.contact = PLACEHOLDER
    lead.email = None
    lead.phone = None
    lead.company = None
    lead.telegram_user_id = None
    lead.notes = None
    lead.specific_need = None
    lead.pain_point = None
    lead.budget = None
    lead.industry = None
    lead.anonymized_at = now
    db.flush()

    # Учётная запись входа по той же почте, если других живых дел у неё нет.
    for email in emails:
        still_used = db.scalar(
            select(func.count()).select_from(Lead).where(
                Lead.anonymized_at.is_(None),
                or_(func.lower(Lead.email) == email, func.lower(func.trim(Lead.contact)) == email),
            )
        )
        if not still_used:
            counts["accounts"] += db.execute(delete(ClientAccount).where(func.lower(ClientAccount.email) == email)).rowcount
    return counts


def _scrub_evidence(db: Session, now: datetime) -> int:
    """NDA и согласия обезличенных клиентов — после срока исковой давности."""
    before = now - timedelta(days=get_settings().prospect_retention_days)
    anonymized = select(Lead.id).where(Lead.anonymized_at.is_not(None))
    scrubbed = db.execute(
        update(NdaSignature)
        .where(NdaSignature.lead_id.in_(anonymized))
        .where(NdaSignature.signed_at < before)
        .where(or_(NdaSignature.signer_full_name.is_not(None), NdaSignature.telegram_user_id.is_not(None),
                   NdaSignature.signer_name.is_not(None), NdaSignature.signer_email.is_not(None)))
        .values(telegram_user_id=None, telegram_username=None, signer_account_id=None, signer_email=None,
                signer_name=None, signer_full_name=None, signer_contact=None, signer_org=None,
                signer_identity_document=None, document_text=None)
    ).rowcount
    scrubbed += db.execute(
        update(NdaPersonalDataConsent)
        .where(NdaPersonalDataConsent.lead_id.in_(anonymized))
        .where(NdaPersonalDataConsent.accepted_at < before)
        .where(NdaPersonalDataConsent.signer_full_name != PLACEHOLDER)
        .values(telegram_user_id=None, telegram_username=None, signer_account_id=None, signer_email=None,
                signer_full_name=PLACEHOLDER, signer_contact=PLACEHOLDER, signer_org=None,
                # Заглушка — не персональные данные: пишем строкой, мимо шифрования
                # (pii.decrypt читает строку без префикса как есть), чтобы проход
                # не зависел от ключа.
                signer_identity_document=literal(PLACEHOLDER, String()), document_text=f"[{PLACEHOLDER}]")
    ).rowcount
    return scrubbed


def _due_evidence(db: Session, now: datetime) -> int:
    before = now - timedelta(days=get_settings().prospect_retention_days)
    anonymized = select(Lead.id).where(Lead.anonymized_at.is_not(None))
    return int(
        db.scalar(
            select(func.count()).select_from(NdaSignature)
            .where(NdaSignature.lead_id.in_(anonymized), NdaSignature.signed_at < before,
                   or_(NdaSignature.signer_full_name.is_not(None), NdaSignature.telegram_user_id.is_not(None)))
        ) or 0
    )


def preview(db: Session, now: datetime | None = None) -> dict:
    """Сколько ждёт обезличивания — без имён. Смотреть перед включением."""
    now = now or datetime.now(timezone.utc)
    settings = get_settings()
    return {
        "enabled": settings.anonymize_enabled,
        "archive_after_days": settings.archive_anonymize_after_days,
        "retention_days": settings.prospect_retention_days,
        "due_leads": len(due_leads(db, now, limit=100_000)),
        "due_evidence": _due_evidence(db, now),
        "anonymized_total": int(db.scalar(select(func.count()).select_from(Lead).where(Lead.anonymized_at.is_not(None))) or 0),
    }


def digest_line(db: Session, now: datetime) -> str | None:
    """Строка еженедельной сводки: что сделано или что ждёт включения."""
    if get_settings().anonymize_enabled:
        done = int(db.scalar(
            select(func.count()).select_from(Lead).where(Lead.anonymized_at >= now - timedelta(days=7))
        ) or 0)
        return f"Обезличено по сроку хранения: {done}" if done else None
    due = len(due_leads(db, now, limit=100_000))
    if not due:
        return None
    return (
        f"По сроку хранения (152-ФЗ) к обезличиванию: {due} клиентов без договора. "
        "Обезличивание выключено — включите ANONYMIZE_ENABLED, когда проверите."
    )


def run(now: datetime | None = None, limit: int = BATCH) -> dict:
    """Из такта ядра: пачка клиентов и доказательства, прошедшие срок."""
    settings = get_settings()
    if not settings.anonymize_enabled:
        return {"enabled": False}
    now = now or datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        ids = due_leads(db, now, limit)
        for lead_id in ids:
            lead = db.get(Lead, lead_id)
            counts = anonymize_lead(db, lead, now)
            write_audit(
                db,
                actor_type=ActorType.system,
                actor_id="anonymization",
                action="lead.anonymize",
                target_type="lead",
                target_id=lead_id,
                details=counts,
            )
        evidence = _scrub_evidence(db, now)
        if ids or evidence:
            parts = []
            if ids:
                parts.append(f"клиентов без договора — {len(ids)}")
            if evidence:
                parts.append(f"NDA и согласий старше трёх лет — {evidence}")
            queue_notice(
                db,
                f"anonymize:{ids[0] if ids else now.date().isoformat()}",
                "Обезличены по сроку хранения (152-ФЗ): " + "; ".join(parts) + ". "
                "Файлы, присланные клиентами, остаются в чате юриста в Telegram — удалите их там вручную.",
            )
        db.commit()
        return {"leads": len(ids), "evidence": evidence}
    except Exception:
        db.rollback()
        logger.exception("anonymization failed")
        raise
    finally:
        db.close()
