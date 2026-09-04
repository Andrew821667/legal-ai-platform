from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.idempotency import cached_response, store_response
from core_api.lead_notifications import notify_new_legal_intake
from core_api.models import (
    ActorType,
    Lead,
    LeadSegment,
    LeadStatus,
    LegalClientType,
    LegalIntake,
    LegalIntakeStatus,
    Scope,
)
from core_api.schemas import (
    LegalIntakeCreate,
    LegalIntakeOut,
    LegalIntakePatch,
    MessageResponse,
)

router = APIRouter(prefix="/api/v1/legal-intakes", tags=["legal-intakes"])


def _segment_for(client_type: LegalClientType) -> LeadSegment:
    if client_type == LegalClientType.company:
        return LeadSegment.inhouse
    if client_type == LegalClientType.entrepreneur:
        return LeadSegment.entrepreneur
    return LeadSegment.other


def _payload(item: LegalIntake, lead: Lead) -> LegalIntakeOut:
    return LegalIntakeOut(
        id=item.id,
        lead_id=item.lead_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        client_type=item.client_type,
        legal_area=item.legal_area,
        description=item.description,
        urgency=item.urgency,
        deadline=item.deadline,
        region=item.region,
        source_context=item.source_context,
        status=item.status,
        conflict_status=item.conflict_status,
        assigned_to=item.assigned_to,
        internal_note=item.internal_note,
        lead_name=lead.name,
        lead_contact=lead.contact,
        lead_company=lead.company,
        lead_source=lead.source,
    )


@router.post("", response_model=LegalIntakeOut, status_code=status.HTTP_201_CREATED)
def create_legal_intake(
    payload: LegalIntakeCreate,
    background_tasks: BackgroundTasks,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> LegalIntakeOut | JSONResponse:
    if idempotency_key:
        cached = cached_response(db, idempotency_key, namespace="legal_intakes.create")
        if cached:
            cached_status, cached_body = cached
            return JSONResponse(status_code=cached_status, content=cached_body)

    consent_note = (
        f"consent=accepted\nconsent_version={payload.consent_version}"
        f"\nconsent_at={payload.consent_at.isoformat()}"
    )
    notes = consent_note if not payload.notes else f"{consent_note}\n{payload.notes}"
    lead = Lead(
        source=payload.source,
        telegram_user_id=payload.telegram_user_id,
        name=payload.name.strip() if payload.name else None,
        contact=payload.contact.strip(),
        company=payload.company.strip() if payload.company else None,
        segment=_segment_for(payload.client_type),
        status=LeadStatus.new,
        service_category=f"legal_help:{payload.legal_area.value}",
        specific_need=payload.description.strip(),
        urgency=payload.urgency.value,
        conversation_stage="legal_intake",
        cta_variant="legal_help",
        notes=notes,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        utm_content=payload.utm_content,
        utm_term=payload.utm_term,
    )
    db.add(lead)
    db.flush()

    item = LegalIntake(
        lead_id=lead.id,
        client_type=payload.client_type,
        legal_area=payload.legal_area,
        description=payload.description.strip(),
        urgency=payload.urgency,
        deadline=payload.deadline.strip() if payload.deadline else None,
        region=payload.region.strip() if payload.region else None,
        source_context=payload.source_context.strip() if payload.source_context else None,
    )
    db.add(item)
    db.flush()
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="legal_intake.create",
        target_type="legal_intake",
        target_id=item.id,
        details={
            "client_type": item.client_type.value,
            "legal_area": item.legal_area.value,
            "urgency": item.urgency.value,
            "source": lead.source.value,
        },
    )
    db.commit()
    db.refresh(lead)
    db.refresh(item)

    result = _payload(item, lead)
    if idempotency_key:
        store_response(
            db,
            idempotency_key,
            status.HTTP_201_CREATED,
            result.model_dump(mode="json"),
            namespace="legal_intakes.create",
        )
    background_tasks.add_task(notify_new_legal_intake, item.id)
    return result


@router.get("", response_model=list[LegalIntakeOut])
def list_legal_intakes(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
    status_filter: LegalIntakeStatus | None = None,
    limit: int = 100,
) -> list[LegalIntakeOut]:
    _ = identity
    query = select(LegalIntake, Lead).join(Lead, Lead.id == LegalIntake.lead_id)
    if status_filter is not None:
        query = query.where(LegalIntake.status == status_filter)
    rows = db.execute(query.order_by(LegalIntake.created_at.desc()).limit(max(1, min(limit, 500)))).all()
    return [_payload(item, lead) for item, lead in rows]


@router.get("/{intake_id}", response_model=LegalIntakeOut)
def get_legal_intake(
    intake_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> LegalIntakeOut:
    _ = identity
    row = db.execute(
        select(LegalIntake, Lead)
        .join(Lead, Lead.id == LegalIntake.lead_id)
        .where(LegalIntake.id == intake_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Legal intake not found")
    return _payload(*row)


@router.patch("/{intake_id}", response_model=LegalIntakeOut)
def update_legal_intake(
    intake_id: uuid.UUID,
    payload: LegalIntakePatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> LegalIntakeOut:
    row = db.execute(
        select(LegalIntake, Lead)
        .join(Lead, Lead.id == LegalIntake.lead_id)
        .where(LegalIntake.id == intake_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Legal intake not found")
    item, lead = row
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(item, key, value)

    if item.status == LegalIntakeStatus.proposal_sent:
        lead.status = LeadStatus.proposal
    elif item.status == LegalIntakeStatus.accepted:
        lead.status = LeadStatus.won
    elif item.status == LegalIntakeStatus.declined:
        lead.status = LeadStatus.lost
    elif item.status in {LegalIntakeStatus.needs_clarification, LegalIntakeStatus.conflict_check}:
        lead.status = LeadStatus.qualified

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="legal_intake.update",
        target_type="legal_intake",
        target_id=item.id,
        details={key: value.value if hasattr(value, "value") else value for key, value in updates.items()},
    )
    db.commit()
    db.refresh(item)
    db.refresh(lead)
    return _payload(item, lead)


@router.get("/outreach/pending", response_model=list[dict])
def list_intakes_pending_outreach(
    delay_minutes: int = 5,
    limit: int = 20,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Обращения, которым пора написать от лица команды.

    Пауза перед первым сообщением нужна, чтобы человек не получил ответ через
    секунду после отправки формы: мгновенная реакция читается как автоответчик
    и обесценивает само обращение.

    Возвращаются только те, кому ещё не писали и по кому не зафиксирована
    причина отказа.
    """
    _ = identity
    from datetime import datetime, timedelta, timezone

    ready_before = datetime.now(timezone.utc) - timedelta(minutes=max(delay_minutes, 0))
    rows = db.execute(
        select(LegalIntake, Lead)
        .join(Lead, Lead.id == LegalIntake.lead_id)
        .where(
            LegalIntake.outreach_sent_at.is_(None),
            LegalIntake.outreach_blocked_reason.is_(None),
            LegalIntake.created_at <= ready_before,
        )
        .order_by(LegalIntake.created_at)
        .limit(max(1, min(limit, 50)))
    ).all()

    return [
        {
            "intake_id": str(item.id),
            "telegram_user_id": lead.telegram_user_id,
            "name": lead.name,
            "client_type": item.client_type.value,
            "legal_area": item.legal_area.value,
            "urgency": item.urgency.value,
            "description": item.description,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item, lead in rows
    ]


@router.post("/{intake_id}/outreach", response_model=MessageResponse)
def mark_intake_outreach(
    intake_id: uuid.UUID,
    payload: dict,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Отмечает результат первого обращения к клиенту.

    Отметка ставится и при успехе, и при отказе: без неё фоновая задача
    вернётся к тому же обращению на следующем круге и напишет повторно.
    """
    from datetime import datetime, timezone

    item = db.get(LegalIntake, intake_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Legal intake not found")

    reason = str(payload.get("blocked_reason") or "").strip()[:64]
    if reason:
        item.outreach_blocked_reason = reason
    else:
        item.outreach_sent_at = datetime.now(timezone.utc)

    db.add(item)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="legal_intake.outreach",
        target_type="legal_intake",
        target_id=item.id,
        details={"blocked_reason": reason or None},
    )
    db.commit()
    return MessageResponse(message="recorded")
