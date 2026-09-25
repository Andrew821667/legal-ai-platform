"""Годовой лимит дохода самозанятого — 2,4 млн ₽ за календарный год.

Превысил — и право на налог на профессиональный доход пропадает до конца
года. Узнать об этом задним числом — худший вариант: система видит каждую
оплату, значит, может и предупредить заранее.

Доход — это поступления, поэтому считаются оплаченные акты по дате оплаты в
текущем году по Москве. Архивные клиенты считаются: деньги от клиента,
которого убрали с глаз, всё равно доход. Не считаются только тесты с
аккаунтов владельца и отозванные акты. Оплаты мимо системы она не видит —
об этом сказано рядом с цифрой.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core_api.client_notices import queue_notice
from core_api.config import get_settings
from core_api.models import Lead, WorkAct, WorkActStatus
from core_api.staff import real_client

_TZ = ZoneInfo("Europe/Moscow")
# Пороги, о которых говорим владельцу: заранее, почти у края и за краем.
THRESHOLDS = (80, 95, 100)


def year_start(now: datetime) -> datetime:
    local = now.astimezone(_TZ)
    return datetime(local.year, 1, 1, tzinfo=_TZ).astimezone(timezone.utc)


def _income(db: Session, since: datetime) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(WorkAct.amount_minor), 0))
        .select_from(WorkAct)
        .outerjoin(Lead, Lead.id == WorkAct.lead_id)
        .where(WorkAct.status == WorkActStatus.paid)
        .where(WorkAct.cancelled_at.is_(None))
        .where(WorkAct.paid_at >= since)
        .where(real_client(Lead.telegram_user_id))
    )
    return int(total or 0)


def level(used_pct: int) -> str:
    if used_pct >= 100:
        return "over"
    if used_pct >= 95:
        return "alert"
    if used_pct >= 80:
        return "warn"
    return "ok"


def summary(db: Session, now: datetime) -> dict:
    limit = max(int(get_settings().npd_annual_limit_minor), 1)
    income = _income(db, year_start(now))
    used_pct = income * 100 // limit
    return {
        "year": now.astimezone(_TZ).year,
        "income_minor": income,
        "limit_minor": limit,
        "left_minor": max(limit - income, 0),
        "used_pct": used_pct,
        "level": level(used_pct),
    }


def _rub(minor: int) -> str:
    return f"{minor // 100:,}".replace(",", " ") + " ₽"


def notice_text(data: dict, threshold: int) -> str:
    head = (
        f"Доход за {data['year']} год — {_rub(data['income_minor'])} "
        f"из {_rub(data['limit_minor'])} лимита самозанятого ({data['used_pct']}%)."
    )
    if threshold >= 100:
        return (
            f"{head} Лимит превышен: право на налог на профессиональный доход "
            "пропадает до конца года. Следующие оплаты стоит принимать уже в другом режиме."
        )
    return (
        f"{head} До лимита осталось {_rub(data['left_minor'])}. Если его превысить, "
        "право на НПД пропадает до конца года — стоит заранее решить, как принимать оплаты дальше."
    )


def notify_if_crossed(db: Session, now: datetime) -> dict:
    """Сказать владельцу о пройденном пороге — один раз за порог и год.

    Только о самом высоком пройденном: сразу два сообщения («80%» и «95%»)
    после одной крупной оплаты — шум. Доход за год только растёт, так что
    пропущенный нижний порог уже не понадобится.
    """
    data = summary(db, now)
    reached = [t for t in THRESHOLDS if data["used_pct"] >= t]
    if reached:
        top = reached[-1]
        queue_notice(db, f"npd_limit:{data['year']}:{top}", notice_text(data, top))
    return data
