from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import ClientNotice, Scope

router = APIRouter(prefix="/api/v1/client-notices", tags=["client-notices"])


@router.post("/claim")
def claim_notices(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = identity
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(ClientNotice)
        .where(
            ClientNotice.delivered_at.is_(None),
            or_(ClientNotice.claim_until.is_(None), ClientNotice.claim_until < now),
        )
        .order_by(ClientNotice.created_at)
        .with_for_update(skip_locked=True)
        .limit(10)
    ).all()
    result = []
    for row in rows:
        row.claim_token = uuid4()
        row.claim_until = now + timedelta(minutes=5)
        result.append(
            {
                "id": str(row.id),
                "claim_token": str(row.claim_token),
                "text": row.text,
                "callback_data": row.callback_data,
            }
        )
    db.commit()
    return result


class Acknowledge(BaseModel):
    claim_token: UUID


@router.post("/{notice_id}/ack")
def acknowledge_notice(
    notice_id: UUID,
    payload: Acknowledge,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    _ = identity
    row = db.scalar(select(ClientNotice).where(ClientNotice.id == notice_id).with_for_update())
    if row is None or row.claim_token != payload.claim_token:
        raise HTTPException(status_code=409, detail="Notification claim has changed")
    row.delivered_at = row.delivered_at or datetime.now(timezone.utc)
    db.commit()
    return {"delivered": True}
