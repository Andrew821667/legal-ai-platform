"""Служебный такт ядра: проверка связи с Telegram и повторы отправок.

Своего планировщика у ядра нет — его дёргает бот раз в пару минут.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core_api import telegram_delivery
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.models import Scope

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


@router.post("/tick")
def tick(identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin))) -> dict:
    _ = identity
    return telegram_delivery.tick()
