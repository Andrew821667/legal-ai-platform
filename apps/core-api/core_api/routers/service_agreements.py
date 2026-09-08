"""Двусторонний договор юридических услуг в Telegram."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.config import get_settings
from core_api.db import get_db
from core_api.idempotency import cached_response, store_response
from core_api.models import (
    ActorType,
    Lead,
    LeadStatus,
    LegalIntake,
    LegalIntakeStatus,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
    ServiceAgreementStatus,
)
from core_api.service_agreement import AGREEMENT_VERSION, document_hash, render_agreement_text

router = APIRouter(prefix="/api/v1/service-agreements", tags=["service-agreements"])

_OPEN = {
    ServiceAgreementStatus.draft,
    ServiceAgreementStatus.sent,
    ServiceAgreementStatus.viewed,
}


class AgreementCreate(BaseModel):
    intake_id: uuid.UUID
    prepared_by_telegram_user_id: int = Field(gt=0)
    subject: str = Field(min_length=10, max_length=4000)
    scope_text: str = Field(min_length=10, max_length=6000)
    exclusions_text: str = Field(min_length=2, max_length=2000)
    schedule_text: str = Field(min_length=2, max_length=2000)
    price_text: str = Field(min_length=2, max_length=500)
    payment_terms: str = Field(min_length=2, max_length=2000)
    expires_in_days: int = Field(default=7, ge=1, le=30)


class DeliveryData(BaseModel):
    chat_id: int
    message_id: int
    telegram_user_id: int = Field(gt=0)
    callback_id: str = Field(min_length=1, max_length=255)


class ClientAction(BaseModel):
    telegram_user_id: int
    document_hash: str = Field(min_length=64, max_length=64)
    message_id: int | None = None
    callback_id: str = Field(min_length=1, max_length=255)


class AgreementSign(ClientAction):
    telegram_username: str | None = Field(default=None, max_length=255)
    signer_position: str | None = Field(default=None, max_length=255)
    authority_basis: str | None = Field(default=None, max_length=500)


class AgreementDecline(BaseModel):
    telegram_user_id: int
    reason: str | None = Field(default=None, max_length=1000)
    callback_id: str = Field(min_length=1, max_length=255)


class AgreementMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    telegram_user_id: int | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _nda_for_lead(db: Session, lead: Lead) -> NdaSignature | None:
    checks = [NdaSignature.lead_id == lead.id]
    if lead.telegram_user_id is not None:
        checks.append(NdaSignature.telegram_user_id == lead.telegram_user_id)
    return db.execute(
        select(NdaSignature).where(or_(*checks)).order_by(NdaSignature.signed_at.desc()).limit(1)
    ).scalar_one_or_none()


def _get(
    db: Session,
    agreement_id: uuid.UUID,
    *,
    lock: bool = False,
) -> ServiceAgreement:
    stmt = select(ServiceAgreement).where(ServiceAgreement.id == agreement_id)
    if lock:
        stmt = stmt.with_for_update()
    item = db.execute(stmt).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if (
        item.status in {ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed}
        and item.expires_at
        and item.expires_at <= _now()
    ):
        item.status = ServiceAgreementStatus.expired
        db.commit()
    return item


def _assert_client(item: ServiceAgreement, telegram_user_id: int) -> None:
    if item.client_telegram_user_id != telegram_user_id:
        raise HTTPException(status_code=403, detail="Agreement belongs to another client")


def _payload(item: ServiceAgreement, *, include_text: bool = False) -> dict:
    client = item.client_snapshot or {}
    data = {
        "id": str(item.id),
        "agreement_number": item.agreement_number,
        "revision": item.revision,
        "lead_id": str(item.lead_id) if item.lead_id else None,
        "intake_id": str(item.intake_id) if item.intake_id else None,
        "status": item.status.value,
        "subject": item.subject,
        "scope_text": item.scope_text,
        "exclusions_text": item.exclusions_text,
        "schedule_text": item.schedule_text,
        "price_text": item.price_text,
        "payment_terms": item.payment_terms,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "sent_at": item.sent_at.isoformat() if item.sent_at else None,
        "viewed_at": item.viewed_at.isoformat() if item.viewed_at else None,
        "signed_at": item.signed_at.isoformat() if item.signed_at else None,
        "declined_at": item.declined_at.isoformat() if item.declined_at else None,
        "client_telegram_user_id": item.client_telegram_user_id,
        "client_name": client.get("full_name"),
        "client_contact": client.get("contact"),
        "client_org": client.get("org"),
        "signer_position": item.signer_position,
        "authority_basis": item.authority_basis,
        "version": item.document_version,
        "hash": item.document_hash,
    }
    if include_text:
        data["text"] = item.document_text
    return data


def _message_payload(item: ServiceAgreementMessage) -> dict:
    return {
        "id": str(item.id),
        "role": item.role.value,
        "telegram_user_id": item.telegram_user_id,
        "text": item.text,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _audit(
    db: Session,
    identity: ApiKeyIdentity,
    item: ServiceAgreement,
    action: str,
    details: dict | None = None,
) -> None:
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action=action,
        target_type="service_agreement",
        target_id=item.id,
        details=details or {},
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=None)
def create_agreement(
    payload: AgreementCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """Создаёт зафиксированную редакцию после NDA и conflict check."""
    if idempotency_key and (
        cached := cached_response(db, idempotency_key, namespace="service_agreements.create")
    ):
        code, body = cached
        return JSONResponse(status_code=code, content=body)

    intake = db.execute(
        select(LegalIntake).where(LegalIntake.id == payload.intake_id).with_for_update()
    ).scalar_one_or_none()
    if intake is None:
        raise HTTPException(status_code=404, detail="Legal intake not found")
    if intake.conflict_status.value != "clear":
        raise HTTPException(status_code=409, detail="Conflict check must be clear")

    lead = db.get(Lead, intake.lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.telegram_user_id is None:
        raise HTTPException(status_code=409, detail="Client has no Telegram dialog")
    nda = _nda_for_lead(db, lead)
    if nda is None:
        raise HTTPException(status_code=409, detail="NDA must be signed first")

    previous = db.execute(
        select(ServiceAgreement)
        .where(ServiceAgreement.intake_id == intake.id)
        .order_by(ServiceAgreement.revision.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if previous and previous.status == ServiceAgreementStatus.signed:
        raise HTTPException(
            status_code=409,
            detail="A signed agreement cannot be replaced; create a new intake",
        )
    revision = (previous.revision + 1) if previous else 1
    number = (
        previous.agreement_number.split("-R", 1)[0]
        if previous
        else (f"AV-{_now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}")
    )
    display_number = f"{number}-R{revision}" if revision > 1 else number
    if previous and previous.status in _OPEN:
        previous.status = ServiceAgreementStatus.superseded

    settings = get_settings()
    operator = {
        "name": settings.operator_name.strip(),
        "status": settings.operator_status.strip(),
        "inn": settings.operator_inn.strip(),
        "details": settings.operator_details.strip(),
    }
    if not operator["name"] or not operator["inn"] or not operator["details"]:
        raise HTTPException(status_code=503, detail="Operator contract details are incomplete")

    client = {
        "full_name": nda.signer_full_name or lead.name or "Заказчик",
        "contact": nda.signer_contact or lead.contact or "",
        "org": nda.signer_org,
        "nda_id": str(nda.id),
        "nda_version": nda.document_version,
    }
    created = _now()
    expires = created + timedelta(days=payload.expires_in_days)
    text = render_agreement_text(
        number=display_number,
        revision=revision,
        created_date=created.strftime("%d.%m.%Y"),
        expires_date=expires.strftime("%d.%m.%Y"),
        operator_name=operator["name"],
        operator_status=operator["status"],
        operator_inn=operator["inn"],
        operator_details=operator["details"],
        client_name=client["full_name"],
        client_org=client["org"],
        subject=payload.subject,
        scope=payload.scope_text,
        exclusions=payload.exclusions_text,
        schedule=payload.schedule_text,
        price=payload.price_text,
        payment_terms=payload.payment_terms,
    )
    item = ServiceAgreement(
        agreement_number=display_number,
        lead_id=lead.id,
        intake_id=intake.id,
        revision=revision,
        supersedes_id=previous.id if previous else None,
        subject=payload.subject.strip(),
        scope_text=payload.scope_text.strip(),
        exclusions_text=payload.exclusions_text.strip(),
        schedule_text=payload.schedule_text.strip(),
        price_text=payload.price_text.strip(),
        payment_terms=payload.payment_terms.strip(),
        created_by=identity.name,
        prepared_by_telegram_user_id=payload.prepared_by_telegram_user_id,
        operator_snapshot=operator,
        client_snapshot=client,
        document_text=text,
        document_version=AGREEMENT_VERSION,
        document_hash=document_hash(text),
        expires_at=expires,
        client_telegram_user_id=lead.telegram_user_id,
    )
    intake.status = LegalIntakeStatus.scope_preparation
    db.add_all([item, intake])
    db.flush()
    _audit(db, identity, item, "service_agreement.create", {"revision": revision})
    body = _payload(item, include_text=True)
    if idempotency_key:
        store_response(
            db,
            idempotency_key,
            status.HTTP_201_CREATED,
            body,
            namespace="service_agreements.create",
        )
    else:
        db.commit()
    return body


@router.get("/by-intake/{intake_id}")
def list_for_intake(
    intake_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = identity
    rows = (
        db.execute(
            select(ServiceAgreement)
            .where(ServiceAgreement.intake_id == intake_id)
            .order_by(ServiceAgreement.revision.desc())
        )
        .scalars()
        .all()
    )
    return [_payload(row) for row in rows]


@router.get("/by-telegram/{telegram_user_id}")
def list_for_client(
    telegram_user_id: int,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(ServiceAgreement).where(
        ServiceAgreement.client_telegram_user_id == telegram_user_id
    )
    if identity.scope == Scope.bot:
        stmt = stmt.where(ServiceAgreement.status != ServiceAgreementStatus.draft)
    rows = db.execute(stmt.order_by(ServiceAgreement.created_at.desc()).limit(20)).scalars().all()
    return [_payload(row) for row in rows]


@router.get("/{agreement_id}")
def get_agreement(
    agreement_id: uuid.UUID,
    telegram_user_id: int | None = Query(default=None),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, agreement_id)
    if identity.scope == Scope.bot:
        if telegram_user_id is None:
            raise HTTPException(status_code=400, detail="telegram_user_id is required")
        _assert_client(item, telegram_user_id)
        if item.status == ServiceAgreementStatus.draft:
            raise HTTPException(status_code=404, detail="Agreement not found")
    return _payload(item, include_text=True)


@router.post("/{agreement_id}/sent")
def mark_sent(
    agreement_id: uuid.UUID,
    payload: DeliveryData,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, agreement_id, lock=True)
    if item.status != ServiceAgreementStatus.draft:
        raise HTTPException(status_code=409, detail="Only a draft can be sent")
    item.status = ServiceAgreementStatus.sent
    item.sent_at = _now()
    item.sent_chat_id = payload.chat_id
    item.sent_message_id = payload.message_id
    item.sent_by_telegram_user_id = payload.telegram_user_id
    item.sent_callback_id = payload.callback_id
    if item.intake_id and (intake := db.get(LegalIntake, item.intake_id)):
        intake.status = LegalIntakeStatus.proposal_sent
    if item.lead_id and (lead := db.get(Lead, item.lead_id)):
        lead.status = LeadStatus.proposal
    _audit(db, identity, item, "service_agreement.sent")
    db.commit()
    return _payload(item)


@router.post("/{agreement_id}/viewed")
def mark_viewed(
    agreement_id: uuid.UUID,
    payload: ClientAction,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, agreement_id, lock=True)
    _assert_client(item, payload.telegram_user_id)
    if item.status not in {ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed}:
        raise HTTPException(status_code=409, detail="Agreement is not available for viewing")
    if payload.document_hash.lower() != item.document_hash:
        raise HTTPException(status_code=409, detail="Document hash mismatch")
    item.status = ServiceAgreementStatus.viewed
    item.viewed_at = item.viewed_at or _now()
    item.viewed_message_id = payload.message_id or item.viewed_message_id
    item.viewed_callback_id = payload.callback_id
    _audit(db, identity, item, "service_agreement.viewed")
    db.commit()
    return _payload(item)


@router.post("/{agreement_id}/sign", status_code=status.HTTP_201_CREATED)
def sign_agreement(
    agreement_id: uuid.UUID,
    payload: AgreementSign,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, agreement_id, lock=True)
    _assert_client(item, payload.telegram_user_id)
    if item.status == ServiceAgreementStatus.signed:
        return {**_payload(item), "already_signed": True}
    if item.status != ServiceAgreementStatus.viewed:
        raise HTTPException(status_code=409, detail="Agreement must be viewed before signing")
    if payload.document_hash.lower() != item.document_hash:
        raise HTTPException(status_code=409, detail="Document hash mismatch")

    client = item.client_snapshot or {}
    if client.get("org") and (not payload.signer_position or not payload.authority_basis):
        raise HTTPException(status_code=422, detail="Position and authority basis are required")

    item.status = ServiceAgreementStatus.signed
    item.signed_at = _now()
    item.signer_telegram_user_id = payload.telegram_user_id
    item.signer_telegram_username = payload.telegram_username
    item.signer_full_name = client.get("full_name")
    item.signer_contact = client.get("contact")
    item.signer_org = client.get("org")
    item.signer_position = payload.signer_position
    item.authority_basis = payload.authority_basis
    item.signed_callback_id = payload.callback_id
    if item.intake_id and (intake := db.get(LegalIntake, item.intake_id)):
        intake.status = LegalIntakeStatus.accepted
    if item.lead_id and (lead := db.get(Lead, item.lead_id)):
        lead.status = LeadStatus.won
    _audit(db, identity, item, "service_agreement.sign", {"version": item.document_version})
    db.commit()
    return {**_payload(item), "already_signed": False}


@router.post("/{agreement_id}/decline")
def decline_agreement(
    agreement_id: uuid.UUID,
    payload: AgreementDecline,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, agreement_id, lock=True)
    _assert_client(item, payload.telegram_user_id)
    if item.status not in {ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed}:
        raise HTTPException(status_code=409, detail="Agreement cannot be declined")
    item.status = ServiceAgreementStatus.declined
    item.declined_at = _now()
    item.decline_reason = payload.reason
    item.declined_callback_id = payload.callback_id
    if item.intake_id and (intake := db.get(LegalIntake, item.intake_id)):
        intake.status = LegalIntakeStatus.scope_preparation
    _audit(db, identity, item, "service_agreement.decline")
    db.commit()
    return _payload(item)


@router.post("/{agreement_id}/questions", status_code=status.HTTP_201_CREATED)
def add_question(
    agreement_id: uuid.UUID,
    payload: AgreementMessageIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, agreement_id, lock=True)
    if payload.telegram_user_id is None:
        raise HTTPException(status_code=422, detail="telegram_user_id is required")
    _assert_client(item, payload.telegram_user_id)
    if item.status not in {ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed}:
        raise HTTPException(status_code=409, detail="Agreement is not open for questions")
    msg = ServiceAgreementMessage(
        agreement_id=item.id,
        role=ServiceAgreementMessageRole.client,
        telegram_user_id=payload.telegram_user_id,
        text=payload.text.strip(),
    )
    db.add(msg)
    db.flush()
    _audit(db, identity, item, "service_agreement.question")
    db.commit()
    return {"id": str(msg.id), "created_at": msg.created_at.isoformat() if msg.created_at else None}


@router.post("/{agreement_id}/replies", status_code=status.HTTP_201_CREATED)
def add_reply(
    agreement_id: uuid.UUID,
    payload: AgreementMessageIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, agreement_id)
    msg = ServiceAgreementMessage(
        agreement_id=item.id,
        role=ServiceAgreementMessageRole.lawyer,
        telegram_user_id=payload.telegram_user_id,
        text=payload.text.strip(),
    )
    db.add(msg)
    db.flush()
    _audit(db, identity, item, "service_agreement.reply")
    db.commit()
    return {"id": str(msg.id), "created_at": msg.created_at.isoformat() if msg.created_at else None}


@router.get("/{agreement_id}/messages")
def list_messages(
    agreement_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = identity
    _get(db, agreement_id)
    rows = (
        db.execute(
            select(ServiceAgreementMessage)
            .where(ServiceAgreementMessage.agreement_id == agreement_id)
            .order_by(ServiceAgreementMessage.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [_message_payload(row) for row in rows]
