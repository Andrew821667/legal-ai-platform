"""Учёт такта ядра: каждый шаг сам по себе и отметка «такт был».

Своего планировщика у ядра нет — такт дёргает бот раз в пару минут. Раньше
исключение в одном шаге (напоминания, сводка, проверка бэкапа…) обрывало
весь такт, и следующие шаги молча не выполнялись. А если бот переставал
дёргать ядро, об этом никто не узнавал: напоминания и сводка просто не
приходили. Теперь сбой шага остаётся в его ответе и в отметке такта, а
отсутствие такта видно снаружи (/health/tick → внешний мониторинг).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from core_api.db import SessionLocal
from core_api.models import ServiceHealth

logger = logging.getLogger(__name__)

TICK_KEY = "core_tick"
# Бот дёргает такт раз в пару минут; 15 минут тишины — уже не случайность.
STALE_AFTER = timedelta(minutes=15)


def run_step(result: dict, name: str, step: Callable[[], object], failed: list[str]) -> None:
    """Выполнить шаг такта; исключение — в лог и в ответ, остальные шаги идут дальше."""
    try:
        result[name] = step()
    except Exception as exc:  # noqa: BLE001 — шаг повторится в следующий такт
        logger.exception("Core tick step failed", extra={"step": name})
        result[name] = {"error": type(exc).__name__}
        failed.append(name)


def record(failed: list[str], now: datetime | None = None) -> None:
    """Отметить такт: когда был и какие шаги упали."""
    now = now or datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        row = db.get(ServiceHealth, TICK_KEY)
        if row is None:
            row = ServiceHealth(key=TICK_KEY)
            db.add(row)
        row.checked_at = now
        row.ok = not failed
        row.last_error = ", ".join(failed)[:500] if failed else None
        row.failing_since = (row.failing_since or now) if failed else None
        db.commit()
    except Exception:  # noqa: BLE001 — отметка не должна ронять сам такт
        logger.exception("Core tick record failed")
        db.rollback()
    finally:
        db.close()


def is_fresh(db, now: datetime | None = None) -> bool:
    """Был ли такт за последние STALE_AFTER."""
    now = now or datetime.now(timezone.utc)
    row = db.get(ServiceHealth, TICK_KEY)
    return bool(row and row.checked_at and now - row.checked_at <= STALE_AFTER)
