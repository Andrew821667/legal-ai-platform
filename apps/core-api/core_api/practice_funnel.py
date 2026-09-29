"""Воронка практики: откуда приходят клиенты и где они останавливаются.

Аналитика в админке заканчивалась статусами лида в CRM («квалифицирован»,
«выигран»), которые никто не ведёт: реальный путь клиента живёт в обращениях,
договорах и актах. Здесь — он: пришёл → оставил обращение → получил договор →
подписал → оплатил, по когорте пришедших за период и по источникам.

Когорта, а не события за период: «из 12 пришедших за месяц оплатили двое» —
это конверсия; «за месяц 12 лидов и 3 оплаты», где оплаты от прошлогодних
клиентов, — нет.

Тестовые аккаунты владельца и клиенты из архива не считаются: архив — это
как раз мусор и проверки, которые юрист убрал с глаз.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core_api.models import (
    ConsultationSlot,
    LegalIntake,
    Lead,
    LeadSource,
    ServiceAgreement,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)
from core_api.staff import real_client

STAGES: list[tuple[str, str]] = [
    ("leads", "Пришли"),
    ("intake", "Оставили обращение"),
    ("agreement", "Получили договор"),
    ("signed", "Подписали"),
    ("paid", "Оплатили"),
]

# Порядок — как на экране. «Бот напрямую» — всё, у чего нет метки: сюда же
# попадает тот, кто прочитал пост и написал боту сам, без кнопки.
SOURCES: list[tuple[str, str]] = [
    ("channel", "Канал"),  # кнопка под постом или через бота-читателя
    ("site_bot", "Сайт → бот"),
    ("site_form", "Форма на сайте"),
    ("miniapp_form", "Форма в мини-аппе"),
    ("bot", "Бот напрямую"),
]

READER_REFERRAL_MARK = "[READER_REFERRAL]"
# Кнопка «Ассистент AI Verdict» прямо под постом в канале (news/publish.py).
CHANNEL_POST_MARK = "[CHANNEL_POST]"
CHANNEL_CTA = {"reader_referral", "channel_post"}


def source_key(source: LeadSource | None, cta_variant: str | None, notes: str | None) -> str:
    """Откуда пришёл клиент — по меткам, которые ставят бот и сайт."""
    if (
        source == LeadSource.telegram_channel
        or cta_variant in CHANNEL_CTA
        or READER_REFERRAL_MARK in (notes or "")
        or CHANNEL_POST_MARK in (notes or "")
    ):
        return "channel"
    if source == LeadSource.website_form:
        return "site_form"
    if source == LeadSource.miniapp_form:
        return "miniapp_form"
    # Кнопки «Написать юристу» на страницах «Юридическая помощь» открывают
    # бота с ?start=legal_help — бот сохраняет это в cta_variant.
    if cta_variant == "legal_help":
        return "site_bot"
    return "bot"


def build(db: Session, *, since: datetime, now: datetime) -> dict:
    leads = db.execute(
        select(Lead.id, Lead.source, Lead.cta_variant, Lead.notes)
        .where(Lead.created_at >= since, Lead.created_at < now)
        .where(Lead.archived_at.is_(None))
        .where(real_client(Lead.telegram_user_id))
    ).all()
    by_lead = {row[0]: source_key(row[1], row[2], row[3]) for row in leads}
    ids = list(by_lead)

    reached: dict[str, set] = {"leads": set(ids)}
    paid_minor: dict = {}
    if ids:
        reached["intake"] = set(
            db.scalars(select(LegalIntake.lead_id).where(LegalIntake.lead_id.in_(ids)).distinct())
        )
        main = (
            select(ServiceAgreement.lead_id)
            .where(ServiceAgreement.lead_id.in_(ids))
            # Допсоглашение — не новая сделка: клиент уже прошёл этот шаг.
            .where(ServiceAgreement.parent_agreement_id.is_(None))
        )
        reached["agreement"] = set(
            db.scalars(main.where(ServiceAgreement.sent_at.is_not(None)).distinct())
        )
        reached["signed"] = set(
            db.scalars(main.where(ServiceAgreement.status == ServiceAgreementStatus.signed).distinct())
        )
        paid_rows = db.execute(
            select(WorkAct.lead_id, func.coalesce(func.sum(WorkAct.amount_minor), 0))
            .where(WorkAct.lead_id.in_(ids))
            .where(WorkAct.status == WorkActStatus.paid)
            .where(WorkAct.cancelled_at.is_(None))
            .group_by(WorkAct.lead_id)
        ).all()
        paid_minor = {row[0]: int(row[1]) for row in paid_rows}
        reached["paid"] = set(paid_minor)
    else:
        for key, _ in STAGES[1:]:
            reached[key] = set()

    def counts(members: set) -> dict[str, int]:
        return {key: len(reached[key] & members) for key, _ in STAGES}

    stages = []
    previous = None
    for key, title in STAGES:
        count = len(reached[key])
        stages.append(
            {
                "key": key,
                "title": title,
                "count": count,
                "from_previous_pct": _pct(count, previous) if previous is not None else None,
            }
        )
        previous = count

    sources = []
    for key, title in SOURCES:
        members = {lead_id for lead_id, source in by_lead.items() if source == key}
        if not members:
            continue
        sources.append(
            {
                "key": key,
                "title": title,
                "counts": counts(members),
                "paid_minor": sum(paid_minor.get(lead_id, 0) for lead_id in members),
            }
        )

    return {
        "since": since.isoformat(),
        "until": now.isoformat(),
        "stages": stages,
        "sources": sources,
        "paid_minor": sum(paid_minor.values()),
        "currency": "RUB",
    }


def revenue_by_source(db: Session, *, since: datetime, until: datetime) -> dict:
    """Деньги за период по источнику клиента: оплаченные акты и консультации.

    Воронка выше считает когорту пришедших; здесь — сколько денег пришло за
    период и от кого, независимо от того, когда клиент появился.
    """
    by_source: dict[str, int] = {}
    acts = db.execute(
        select(WorkAct.amount_minor, Lead.source, Lead.cta_variant, Lead.notes)
        .join(Lead, Lead.id == WorkAct.lead_id)
        .where(WorkAct.status == WorkActStatus.paid)
        .where(WorkAct.cancelled_at.is_(None))
        .where(WorkAct.paid_at >= since, WorkAct.paid_at < until)
        .where(Lead.archived_at.is_(None))
        .where(real_client(Lead.telegram_user_id))
    ).all()
    for amount, *lead in acts:
        key = source_key(*lead)
        by_source[key] = by_source.get(key, 0) + int(amount or 0)
    consultations = db.execute(
        select(ConsultationSlot.price_minor, Lead.source, Lead.cta_variant, Lead.notes)
        .outerjoin(Lead, Lead.id == ConsultationSlot.lead_id)
        .where(ConsultationSlot.status == "confirmed")
        .where(ConsultationSlot.confirmed_at >= since, ConsultationSlot.confirmed_at < until)
        .where(or_(Lead.id.is_(None), Lead.archived_at.is_(None)))
        .where(real_client(Lead.telegram_user_id))
    ).all()
    consultations_minor = 0
    for price, source, cta_variant, notes in consultations:
        # Запись на консультацию идёт с сайта; без лида — туда же.
        key = source_key(source, cta_variant, notes) if source is not None else "site_form"
        by_source[key] = by_source.get(key, 0) + int(price or 0)
        consultations_minor += int(price or 0)
    return {
        "by_source": by_source,
        "total_minor": sum(by_source.values()),
        "consultations": {"count": len(consultations), "minor": consultations_minor},
    }


def cta_variants(db: Session, *, since: datetime, until: datetime) -> dict[str, dict[str, int]]:
    """A/B-варианты призыва в боте: сколько пришло за период и сколько дошло до обращения.

    Вариант бот ставит лиду при первом показе призыва (funnel.choose_cta_variant);
    метки каналов и сайта (channel_post, legal_help…) — не A/B, их здесь нет.
    """
    rows = db.execute(
        select(Lead.id, Lead.cta_variant)
        .where(Lead.created_at >= since, Lead.created_at < until)
        .where(Lead.cta_variant.in_(("A", "B")))
        .where(Lead.archived_at.is_(None))
        .where(real_client(Lead.telegram_user_id))
    ).all()
    ids = [row[0] for row in rows]
    with_intake = (
        set(db.scalars(select(LegalIntake.lead_id).where(LegalIntake.lead_id.in_(ids)).distinct())) if ids else set()
    )
    result: dict[str, dict[str, int]] = {}
    for lead_id, variant in rows:
        bucket = result.setdefault(variant, {"leads": 0, "intakes": 0})
        bucket["leads"] += 1
        bucket["intakes"] += int(lead_id in with_intake)
    return result


def _pct(part: int, whole: int) -> int | None:
    return round(part * 100 / whole) if whole else None


def period_start(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)
