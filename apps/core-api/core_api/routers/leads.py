from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.idempotency import cached_response, store_response
from core_api.lead_notifications import notify_new_lead
from core_api.models import ActorType, ContractJob, Event, Lead, LeadSource, LeadStatus, Scope
from core_api.schemas import LEAD_UPSERT_FLAGS, LeadCreate, LeadOut, LeadPatch, LeadStatsOut, LegacySequenceHandover

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.post("", response_model=LeadOut)
def upsert_lead(
    payload: LeadCreate,
    background_tasks: BackgroundTasks,
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
        if lead is None and payload.claim_unlinked and payload.telegram_user_id is not None:
            # Перенос из SQLite бота: лид этого аккаунта уже есть в ядре (его
            # завело обращение), но номера у него нет — присваиваем, а не
            # заводим второго человека с теми же данными.
            lead = db.execute(
                select(Lead)
                .where(Lead.telegram_user_id == payload.telegram_user_id, Lead.legacy_lead_id.is_(None))
                .order_by(Lead.created_at)
                .limit(1)
            ).scalar_one_or_none()
    elif payload.force_new:
        lead = None
    elif payload.telegram_user_id is not None:
        # Последний лид аккаунта: у постоянного клиента их несколько, и
        # обновлять надо текущий разговор, а не первый попавшийся.
        lead = db.execute(
            select(Lead)
            .where(Lead.telegram_user_id == payload.telegram_user_id)
            .order_by(Lead.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    elif payload.contact:
        lead = db.execute(select(Lead).where(Lead.contact == payload.contact).limit(1)).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    is_new_lead = lead is None
    if lead is None and payload.update_only:
        raise HTTPException(status_code=404, detail="Lead not found")
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
            last_message_at=payload.last_message_at,
            notification_sent=bool(payload.notification_sent),
            team_size=payload.team_size,
            contracts_per_month=payload.contracts_per_month,
        )
        if payload.created_at is not None:
            lead.created_at = payload.created_at
        db.add(lead)
    else:
        # Только то, что прислали явно: бот обновляет лид по одному полю
        # (время последнего сообщения, шаг воронки), и значения по умолчанию
        # схемы — status=new, cta_shown=False — не должны затирать живые.
        payload_data = payload.model_dump(exclude_unset=True, exclude_none=True, exclude=LEAD_UPSERT_FLAGS)
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

    if is_new_lead and lead.source != LeadSource.telegram_bot:
        background_tasks.add_task(notify_new_lead, lead.id)

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
    offset: int = 0,
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
    query = query.order_by(Lead.created_at.desc()).offset(max(0, offset)).limit(capped_limit)
    return list(db.execute(query).scalars().all())


@router.post("/legacy-sequence", response_model=dict)
def handover_legacy_sequence(
    payload: LegacySequenceHandover,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Сдвигает счётчик номеров лидов вперёд — при переносе лидов из SQLite бота.

    Номера в SQLite бота могли уйти дальше, чем известно ядру (лиды, которые
    так и не были отражены). Бот один раз сообщает свой максимум, и новые
    номера начинаются после него: аналитика бота хранит номера, и пересечение
    старого с новым перепутало бы события двух разных людей. Назад счётчик
    не двигается.
    """
    _ = identity
    next_value = db.scalar(
        sa_text(
            "SELECT setval('lead_legacy_id_seq', "
            "GREATEST(CASE WHEN is_called THEN last_value ELSE last_value - 1 END, :floor, 1), true) + 1 "
            "FROM lead_legacy_id_seq"
        ),
        {"floor": payload.min_next - 1},
    )
    db.commit()
    return {"next_legacy_lead_id": int(next_value)}


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


@router.get("/notifications/pending", response_model=list[LeadOut])
def pending_lead_notifications(
    idle_minutes: int = 5,
    limit: int = 20,
    source_filter: LeadSource | None = None,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[Lead]:
    _ = identity
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, min(idle_minutes, 1440)))
    ready = select(Lead).where(
        Lead.last_message_at.is_not(None),
        Lead.last_message_at <= cutoff,
        Lead.notification_sent.is_(False),
        Lead.archived_at.is_(None),
        (
            Lead.temperature.in_(("warm", "hot"))
            | (
                Lead.name.is_not(None)
                & (Lead.email.is_not(None) | Lead.phone.is_not(None) | Lead.contact.is_not(None))
                & Lead.pain_point.is_not(None)
            )
        ),
    )
    if source_filter is not None:
        ready = ready.where(Lead.source == source_filter)
    return list(db.scalars(ready.order_by(Lead.last_message_at).limit(max(1, min(limit, 100)))))


@router.post("/{lead_id}/notification-sent", response_model=LeadOut)
def mark_notification_sent(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> Lead:
    lead = db.scalar(select(Lead).where(Lead.id == lead_id).with_for_update())
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.notification_sent:
        lead.notification_sent = True
        lead.notification_sent_at = datetime.now(timezone.utc)
        write_audit(
            db, actor_type=ActorType.api_key, actor_id=identity.name,
            action="lead.notification_sent", target_type="lead", target_id=lead.id,
        )
        db.commit()
        db.refresh(lead)
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

    detached_events = (
        db.execute(update(Event).where(Event.lead_id == lead_id).values(lead_id=None)).rowcount or 0
    )
    detached_contract_jobs = (
        db.execute(update(ContractJob).where(ContractJob.lead_id == lead_id).values(lead_id=None)).rowcount or 0
    )

    db.delete(lead)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="lead.delete",
        target_type="lead",
        target_id=lead_id,
        details={
            "detached_events": detached_events,
            "detached_contract_jobs": detached_contract_jobs,
        },
    )
    db.commit()
    return Response(status_code=204)
