"""Служебный такт ядра: проверка связи с Telegram, повторы отправок и
автонапоминания клиентам о неподписанных договорах.

Своего планировщика у ядра нет — его дёргает бот раз в пару минут.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core_api import agreement_reminders, telegram_delivery
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
    return result
