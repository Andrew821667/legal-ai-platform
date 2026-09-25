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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core_api.models import (
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
    ("channel", "Канал"),
    ("site_bot", "Сайт → бот"),
    ("site_form", "Форма на сайте"),
    ("miniapp_form", "Форма в мини-аппе"),
    ("bot", "Бот напрямую"),
]

READER_REFERRAL_MARK = "[READER_REFERRAL]"


def source_key(source: LeadSource | None, cta_variant: str | None, notes: str | None) -> str:
    """Откуда пришёл клиент — по меткам, которые ставят бот и сайт."""
    if (
        source == LeadSource.telegram_channel
        or cta_variant == "reader_referral"
        or READER_REFERRAL_MARK in (notes or "")
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


def _pct(part: int, whole: int) -> int | None:
    return round(part * 100 / whole) if whole else None


def period_start(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)
