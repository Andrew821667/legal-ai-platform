"""Сводка за неделю — владельцу в Telegram, по понедельникам.

Всё, что в ней есть, уже видно в рабочем месте, но туда надо зайти. Раз в
неделю практика сама отчитывается одним сообщением: кто пришёл, что
подписано и оплачено, сколько должны и что ждёт вас прямо сейчас. Если за
неделю ничего не произошло, это тоже сигнал — сводка приходит и тогда.

Отправляется через очередь уведомлений, её доставляет бот. Ставит в очередь
такт ядра (см. telegram_ops): в первый такт после понедельника 09:00 по
Москве. Ключ недели в очереди уникален, поэтому второй раз не придёт, а если
бот лежал в понедельник — придёт, когда поднимется.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core_api import anonymization, backup_health, practice_funnel
from core_api.client_notices import queue_notice
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.models import (
    ClientNotice,
    LegalIntake,
    Lead,
    ServiceAgreement,
    ServiceAgreementStatus,
    WorkActStatus,
)
from core_api.staff import real_client

_TZ = ZoneInfo("Europe/Moscow")
SEND_HOUR = 9


def _rub(minor: int) -> str:
    return f"{minor // 100:,}".replace(",", " ") + " ₽"


def _acts(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} акт"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} акта"
    return f"{n} актов"


def week_start(now: datetime) -> datetime:
    """Понедельник 00:00 по Москве той недели, в которой now."""
    local = now.astimezone(_TZ)
    monday = (local - timedelta(days=local.weekday())).date()
    return datetime(monday.year, monday.month, monday.day, tzinfo=_TZ).astimezone(timezone.utc)


def week_key(now: datetime) -> str:
    year, week, _ = now.astimezone(_TZ).isocalendar()
    return f"weekly_digest:{year}-W{week:02d}"


def is_due(now: datetime) -> bool:
    local = now.astimezone(_TZ)
    return local.weekday() > 0 or local.hour >= SEND_HOUR


def build(db: Session, now: datetime) -> str:
    # Лениво: роутер рабочего места импортирует много, а считать деньги и
    # задачи надо ровно так же, как экран, — не второй копией.
    from core_api.routers.lawyer_workspace.money import _counted_acts, _not_archived_agreement, _overdue
    from core_api.routers.lawyer_workspace.today import today

    until = week_start(now)
    since = until - timedelta(days=7)
    period = f"{since.astimezone(_TZ):%d.%m}–{(until - timedelta(seconds=1)).astimezone(_TZ):%d.%m}"

    leads = db.execute(
        select(Lead.source, Lead.cta_variant, Lead.notes)
        .where(Lead.created_at >= since, Lead.created_at < until)
        .where(Lead.archived_at.is_(None))
        .where(real_client(Lead.telegram_user_id))
    ).all()
    sources = Counter(practice_funnel.source_key(*row) for row in leads)
    titles = dict(practice_funnel.SOURCES)

    intakes = db.scalar(
        select(func.count())
        .select_from(LegalIntake)
        .join(Lead, Lead.id == LegalIntake.lead_id)
        .where(LegalIntake.created_at >= since, LegalIntake.created_at < until)
        .where(Lead.archived_at.is_(None))
        .where(real_client(Lead.telegram_user_id))
    ) or 0

    main = (
        select(func.count(), func.coalesce(func.sum(ServiceAgreement.amount_minor), 0))
        .where(ServiceAgreement.parent_agreement_id.is_(None))
        .where(_not_archived_agreement())
    )
    sent_count, _ = db.execute(
        main.where(ServiceAgreement.sent_at >= since, ServiceAgreement.sent_at < until)
    ).one()
    signed_count, signed_minor = db.execute(
        main.where(ServiceAgreement.status == ServiceAgreementStatus.signed)
        .where(ServiceAgreement.signed_at >= since, ServiceAgreement.signed_at < until)
    ).one()

    acts = db.execute(_counted_acts()).all()
    paid = [a for a, _ in acts if a.status == WorkActStatus.paid and a.paid_at and since <= a.paid_at < until]
    open_acts = [a for a, _ in acts if a.status in (WorkActStatus.sent, WorkActStatus.claimed_paid)]
    overdue = [a for a in open_acts if _overdue(a, now)]

    lines = [f"Неделя {period} в практике", ""]
    if leads:
        by_source = ", ".join(f"{titles[key].lower()} — {n}" for key, _ in practice_funnel.SOURCES if (n := sources[key]))
        lines.append(f"Новых клиентов: {len(leads)} ({by_source})")
    else:
        lines.append("Новых клиентов не было.")
    lines.append(f"Обращений: {intakes}")
    lines.append(f"Договоров отправлено: {sent_count}, подписано: {signed_count}" + (f" на {_rub(int(signed_minor))}" if signed_minor else ""))
    lines.append(
        f"Оплачено: {_acts(len(paid))} на {_rub(sum(a.amount_minor for a in paid))}"
        if paid
        else "Оплат не было."
    )
    if open_acts:
        tail = f", из них просрочено {len(overdue)}" if overdue else ""
        lines.append(f"Ждут оплаты: {len(open_acts)} на {_rub(sum(a.amount_minor for a in open_acts))}{tail}")

    tasks = []
    for section in today(identity=None, db=db)["sections"]:
        count = sum(1 for item in section["items"] if not item.get("is_test"))
        if count:
            tasks.append(f"— {section['title']}: {count}")
    lines.append("")
    if tasks:
        lines.append("Ждёт вас сейчас:")
        lines.extend(tasks)
    else:
        lines.append("Задач, которые ждут вас, нет.")
    backup = backup_health.digest_line(db, now)
    if backup:
        lines += ["", backup]
    retention = anonymization.digest_line(db, now)
    if retention:
        lines += ["", retention]
    base = (get_settings().lead_notify_web_base_url or "").rstrip("/")
    if base:
        lines += ["", f"Рабочее место: {base}/lawyer"]
    return "\n".join(lines)


def maybe_queue(now: datetime | None = None) -> dict:
    """Ставит сводку прошлой недели в очередь, если пора и её ещё не было."""
    if not get_settings().weekly_digest_enabled:
        return {"skipped": "disabled"}
    now = now or datetime.now(timezone.utc)
    if not is_due(now):
        return {"skipped": "not_yet"}
    key = week_key(now)
    db = SessionLocal()
    try:
        if db.scalar(select(ClientNotice.id).where(ClientNotice.event_key == key)):
            return {"skipped": "sent"}
        queue_notice(db, key, build(db, now))
        db.commit()
        return {"queued": key}
    finally:
        db.close()
