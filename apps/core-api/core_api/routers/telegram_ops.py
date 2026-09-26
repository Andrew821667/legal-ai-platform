"""Служебный такт ядра: проверка связи с Telegram, повторы отправок и
автонапоминания клиентам о неподписанных договорах.

Своего планировщика у ядра нет — его дёргает бот раз в пару минут.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core_api import agreement_reminders, anonymization, client_reviews, deletion_log, telegram_delivery, weekly_digest
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.models import Scope

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


@router.post("/tick")
def tick(identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin))) -> dict:
    _ = identity
    result = telegram_delivery.tick()
    # Без связи напоминание не дойдёт, а отметка «напомнили» уже встанет.
    result["agreement_reminders"] = (
        agreement_reminders.process_due() if result["health"].get("ok") else {"skipped": "no_link"}
    )
    result["review_requests"] = (
        client_reviews.process_due() if result["health"].get("ok") else {"skipped": "no_link"}
    )
    # Сводка идёт через очередь уведомлений — её доставляет бот своей дорогой,
    # поэтому от связи ядра с Telegram она не зависит.
    result["weekly_digest"] = weekly_digest.maybe_queue()
    # Удаления мимо приложения (psql, скрипт) — сразу владельцу.
    result["deletions"] = deletion_log.watch()
    # Персональные данные с истёкшим сроком хранения — обезличить (152-ФЗ).
    # Сбой здесь не должен останавливать остальной такт.
    try:
        result["anonymized"] = anonymization.run()
    except Exception as exc:  # noqa: BLE001 — уже в логе, повторим в следующий такт
        result["anonymized"] = {"error": type(exc).__name__}
    return result
