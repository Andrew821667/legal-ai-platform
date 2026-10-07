"""Служебный такт ядра: проверка связи с Telegram, повторы отправок и
автонапоминания клиентам о неподписанных договорах.

Своего планировщика у ядра нет — его дёргает бот раз в пару минут.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core_api import (
    agreement_reminders,
    anonymization,
    backup_health,
    client_reviews,
    core_tick,
    deletion_log,
    telegram_delivery,
    weekly_digest,
)
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.models import Scope

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


@router.post("/tick")
def tick(identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin))) -> dict:
    _ = identity
    failed: list[str] = []
    result: dict = {}
    core_tick.run_step(result, "telegram", telegram_delivery.tick, failed)
    telegram = result.pop("telegram")
    if "error" in telegram:
        telegram = {"health": {"ok": False, "error": telegram["error"]}, "due": {"skipped": True}}
    result.update(telegram)
    link_ok = bool(result["health"].get("ok"))
    # Без связи напоминание не дойдёт, а отметка «напомнили» уже встанет.
    if link_ok:
        core_tick.run_step(result, "agreement_reminders", agreement_reminders.process_due, failed)
        core_tick.run_step(result, "review_requests", client_reviews.process_due, failed)
    else:
        result["agreement_reminders"] = {"skipped": "no_link"}
        result["review_requests"] = {"skipped": "no_link"}
    # Сводка идёт через очередь уведомлений — её доставляет бот своей дорогой,
    # поэтому от связи ядра с Telegram она не зависит.
    core_tick.run_step(result, "weekly_digest", weekly_digest.maybe_queue, failed)
    # Удаления мимо приложения (psql, скрипт) — сразу владельцу.
    core_tick.run_step(result, "deletions", deletion_log.watch, failed)
    # Бэкап делает ночная задача на хосте; здесь — не пропал ли он.
    core_tick.run_step(result, "backup", backup_health.check, failed)
    # И ежемесячные учения по восстановлению копии — не пропали ли они.
    core_tick.run_step(result, "restore_drill", backup_health.check_drill, failed)
    # Персональные данные с истёкшим сроком хранения — обезличить (152-ФЗ).
    core_tick.run_step(result, "anonymized", anonymization.run, failed)
    core_tick.record(failed)
    return result
