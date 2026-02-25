from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.idempotency import cached_response, store_response
from core_api.models import ActorType, Lead, Scope
from core_api.schemas import LeadCreate, LeadOut, LeadPatch

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.post("", response_model=LeadOut)
def upsert_lead(
    payload: LeadCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Lead:
    if idempotency_key:
        cached = cached_response(db, idempotency_key)
        if cached:
            cached_status, cached_body = cached
            return JSONResponse(status_code=cached_status, content=cached_body)

    lead = None
    if payload.telegram_user_id is not None:
        lead = db.execute(
            select(Lead).where(Lead.telegram_user_id == payload.telegram_user_id).limit(1)
        ).scalar_one_or_none()
    elif payload.contact:
        lead = db.execute(select(Lead).where(Lead.contact == payload.contact).limit(1)).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if lead is None:
        lead = Lead(
            source=payload.source,
            telegram_user_id=payload.telegram_user_id,
            name=payload.name,
            contact=payload.contact,
            segment=payload.segment,
            status=payload.status,
            score=payload.score,
            notes=payload.notes,
            utm_source=payload.utm_source,
            utm_medium=payload.utm_medium,
            utm_campaign=payload.utm_campaign,
            utm_content=payload.utm_content,
            utm_term=payload.utm_term,
            last_activity_at=now,
        )
        db.add(lead)
    else:
        lead.source = payload.source
        lead.telegram_user_id = payload.telegram_user_id or lead.telegram_user_id
        lead.name = payload.name or lead.name
        lead.contact = payload.contact or lead.contact
        lead.segment = payload.segment or lead.segment
        lead.status = payload.status or lead.status
        lead.score = payload.score if payload.score is not None else lead.score
        lead.notes = payload.notes or lead.notes
        lead.utm_source = payload.utm_source or lead.utm_source
        lead.utm_medium = payload.utm_medium or lead.utm_medium
        lead.utm_campaign = payload.utm_campaign or lead.utm_campaign
        lead.utm_content = payload.utm_content or lead.utm_content
        lead.utm_term = payload.utm_term or lead.utm_term
        lead.last_activity_at = now

    db.commit()
    db.refresh(lead)

    if idempotency_key:
        store_response(
            db,
            idempotency_key,
            status.HTTP_200_OK,
            LeadOut.model_validate(lead).model_dump(mode="json"),
        )

    return lead


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> Lead:
    _ = identity
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadOut)
def patch_lead(
    lead_id: uuid.UUID,
    payload: LeadPatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(lead, key, value)

    db.add(lead)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="lead.update",
        target_type="lead",
        target_id=lead.id,
        details=updates,
    )
    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=204)
def delete_lead(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> Response:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    db.delete(lead)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="lead.delete",
        target_type="lead",
        target_id=lead_id,
    )
    db.commit()
    return Response(status_code=204)
