"""Не доставлено в Telegram: повторить или скрыть отправку."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api import telegram_delivery
from core_api.db import get_db
from core_api.models import (
    Scope,
    TelegramDelivery,
)

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


# --- Не доставлено в Telegram -----------------------------------------------


@router.post("/deliveries/{delivery_id}/retry")
def retry_delivery(
    delivery_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
) -> dict:
    """Повторить уведомление сейчас. Договор, ответ и акт так не повторяются:
    их отправляют из карточки, чтобы клиент не получил дубль."""
    _ = identity
    status = telegram_delivery.retry_now(delivery_id)
    if status == "missing":
        raise HTTPException(status_code=404, detail="Delivery not found")
    if status == "not_retryable":
        raise HTTPException(status_code=409, detail="Send it again from the client card")
    return {"delivery_id": str(delivery_id), "status": status}


@router.post("/deliveries/{delivery_id}/dismiss")
def dismiss_delivery(
    delivery_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Убрать из «Не доставлено»: отправка потеряла смысл."""
    _ = identity
    row = db.get(TelegramDelivery, delivery_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    row.dismissed_at = row.dismissed_at or datetime.now(timezone.utc)
    if row.status == "pending":
        row.status = "failed"
        row.next_attempt_at = None
    db.commit()
    return {"delivery_id": str(delivery_id), "dismissed": True}
