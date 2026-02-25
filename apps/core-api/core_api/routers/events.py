from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.idempotency import cached_response, store_response
from core_api.models import Event, Lead, Scope
from core_api.schemas import EventCreate, EventOut

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("", response_model=EventOut)
def create_event(
    payload: EventCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Event:
    _ = identity
    if idempotency_key:
        cached = cached_response(db, idempotency_key)
        if cached:
            cached_status, cached_body = cached
            return JSONResponse(status_code=cached_status, content=cached_body)

    event = Event(lead_id=payload.lead_id, user_id=payload.user_id, type=payload.type, payload=payload.payload)
    db.add(event)

    if payload.lead_id:
        lead = db.get(Lead, payload.lead_id)
        if lead:
            lead.last_activity_at = datetime.now(timezone.utc)
            db.add(lead)

    db.commit()
    db.refresh(event)

    if idempotency_key:
        store_response(db, idempotency_key, 200, EventOut.model_validate(event).model_dump(mode="json"))

    return event
