from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.idempotency import cached_response, store_response
from core_api.models import ActorType, Lead, LeadSource, LeadStatus, Scope
from core_api.schemas import LeadCreate, LeadOut, LeadPatch, LeadStatsOut

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.post("", response_model=LeadOut)
def upsert_lead(
    payload: LeadCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Lead:
    if idempotency_key:
        cached = cached_response(db, idempotency_key, namespace="leads.upsert")
        if cached:
            cached_status, cached_body = cached
            return JSONResponse(status_code=cached_status, content=cached_body)

    lead = None
    if payload.legacy_lead_id is not None:
        lead = db.execute(select(Lead).where(Lead.legacy_lead_id == payload.legacy_lead_id).limit(1)).scalar_one_or_none()
    elif payload.telegram_user_id is not None:
        lead = db.execute(
            select(Lead).where(Lead.telegram_user_id == payload.telegram_user_id).limit(1)
        ).scalar_one_or_none()
    elif payload.contact:
        lead = db.execute(select(Lead).where(Lead.contact == payload.contact).limit(1)).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if lead is None:
        lead = Lead(
            source=payload.source,
            legacy_lead_id=payload.legacy_lead_id,
            telegram_user_id=payload.telegram_user_id,
            name=payload.name,
            contact=payload.contact,
            company=payload.company,
            email=payload.email,
            phone=payload.phone,
            segment=payload.segment,
            status=payload.status,
            score=payload.score,
            temperature=payload.temperature,
            service_category=payload.service_category,
            specific_need=payload.specific_need,
            pain_point=payload.pain_point,
            budget=payload.budget,
            urgency=payload.urgency,
            industry=payload.industry,
            conversation_stage=payload.conversation_stage,
            cta_variant=payload.cta_variant,
            cta_shown=payload.cta_shown,
            lead_magnet_type=payload.lead_magnet_type,
            lead_magnet_delivered=payload.lead_magnet_delivered,
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
        payload_data = payload.model_dump(exclude_none=True)
        for key, value in payload_data.items():
            setattr(lead, key, value)
        lead.last_activity_at = now

    db.commit()
    db.refresh(lead)

    if idempotency_key:
        store_response(
            db,
            idempotency_key,
            status.HTTP_200_OK,
            LeadOut.model_validate(lead).model_dump(mode="json"),
            namespace="leads.upsert",
        )

    return lead


@router.get("", response_model=list[LeadOut])
def list_leads(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
    status_filter: LeadStatus | None = None,
    source_filter: LeadSource | None = None,
    temperature_filter: str | None = None,
    telegram_user_id: int | None = None,
    legacy_lead_id: int | None = None,
    limit: int = 100,
) -> list[Lead]:
    _ = identity
    capped_limit = max(1, min(limit, 500))
    query = select(Lead)
    if status_filter is not None:
        query = query.where(Lead.status == status_filter)
    if source_filter is not None:
        query = query.where(Lead.source == source_filter)
    if temperature_filter:
        query = query.where(Lead.temperature == temperature_filter)
    if telegram_user_id is not None:
        query = query.where(Lead.telegram_user_id == telegram_user_id)
    if legacy_lead_id is not None:
        query = query.where(Lead.legacy_lead_id == legacy_lead_id)
    query = query.order_by(Lead.created_at.desc()).limit(capped_limit)
    return list(db.execute(query).scalars().all())


@router.get("/stats/summary", response_model=LeadStatsOut)
def leads_summary(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> LeadStatsOut:
    _ = identity
    rows = db.execute(
        select(Lead.status, func.count()).group_by(Lead.status)
    ).all()
    counts = {status.value: total for status, total in rows}
    total_leads = sum(counts.values())
    temperature_rows = db.execute(
        select(Lead.temperature, func.count()).where(Lead.temperature.is_not(None)).group_by(Lead.temperature)
    ).all()
    temperature_counts = {temperature: total for temperature, total in temperature_rows if temperature}
    stage_rows = db.execute(
        select(Lead.conversation_stage, func.count())
        .where(Lead.conversation_stage.is_not(None))
        .group_by(Lead.conversation_stage)
    ).all()
    stage_counts = {stage: total for stage, total in stage_rows if stage}
    telegram_bot_leads = db.execute(
        select(func.count()).select_from(Lead).where(Lead.source == LeadSource.telegram_bot)
    ).scalar_one()

    return LeadStatsOut(
        total_leads=total_leads,
        new_leads=counts.get(LeadStatus.new.value, 0),
        qualified_leads=counts.get(LeadStatus.qualified.value, 0),
        booked_leads=counts.get(LeadStatus.booked.value, 0),
        proposal_leads=counts.get(LeadStatus.proposal.value, 0),
        won_leads=counts.get(LeadStatus.won.value, 0),
        lost_leads=counts.get(LeadStatus.lost.value, 0),
        telegram_bot_leads=telegram_bot_leads,
        hot_leads=temperature_counts.get("hot", 0),
        warm_leads=temperature_counts.get("warm", 0),
        cold_leads=temperature_counts.get("cold", 0),
        stage_discover=stage_counts.get("discover", 0),
        stage_diagnose=stage_counts.get("diagnose", 0),
        stage_qualify=stage_counts.get("qualify", 0),
        stage_propose=stage_counts.get("propose", 0),
        stage_handoff=stage_counts.get("handoff", 0),
    )


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
