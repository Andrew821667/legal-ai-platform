from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import (
    IntakeDocument,
    Lead,
    LegalIntake,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)

router = APIRouter(prefix="/api/v1/client-portal", tags=["client-portal"])


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@router.get("/summary")
def summary(
    telegram_user_id: int = Query(gt=0),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    _ = identity
    leads = db.scalars(
        select(Lead)
        .where(Lead.telegram_user_id == telegram_user_id)
        .order_by(Lead.created_at.desc())
    ).all()
    lead_ids = [row.id for row in leads]
    intakes = db.scalars(
        select(LegalIntake)
        .where(LegalIntake.lead_id.in_(lead_ids))
        .order_by(LegalIntake.created_at.desc())
    ).all() if lead_ids else []
    intake_ids = [row.id for row in intakes]
    documents: dict = {}
    if intake_ids:
        for row in db.scalars(
            select(IntakeDocument)
            .where(IntakeDocument.intake_id.in_(intake_ids))
            .order_by(IntakeDocument.created_at)
        ):
            documents.setdefault(row.intake_id, []).append({
                "id": str(row.id), "file_name": row.file_name,
                "file_size": row.file_size, "mime_type": row.mime_type,
                "created_at": _iso(row.created_at),
            })
    agreements = db.scalars(
        select(ServiceAgreement)
        .where(
            ServiceAgreement.client_telegram_user_id == telegram_user_id,
            ServiceAgreement.status.not_in(
                {ServiceAgreementStatus.draft, ServiceAgreementStatus.superseded}
            ),
        )
        .order_by(ServiceAgreement.created_at.desc())
    ).all()
    agreement_ids = [row.id for row in agreements]
    acts = db.scalars(
        select(WorkAct)
        .where(
            WorkAct.agreement_id.in_(agreement_ids),
            WorkAct.status != WorkActStatus.draft,
        )
        .order_by(WorkAct.created_at.desc())
    ).all() if agreement_ids else []
    messages: dict = {}
    if agreement_ids:
        for row in db.scalars(
            select(ServiceAgreementMessage)
            .where(ServiceAgreementMessage.agreement_id.in_(agreement_ids))
            .order_by(ServiceAgreementMessage.created_at)
        ):
            messages.setdefault(row.agreement_id, []).append({
                "id": str(row.id), "role": row.role.value,
                "text": row.text, "created_at": _iso(row.created_at),
            })
    nda = db.scalar(
        select(NdaSignature)
        .where(or_(NdaSignature.telegram_user_id == telegram_user_id,
                   NdaSignature.lead_id.in_(lead_ids)))
        .order_by(NdaSignature.signed_at.desc())
        .limit(1)
    ) if lead_ids else None
    return {
        "client": {
            "lead_id": str(leads[0].id) if leads else None,
            "name": next((row.name for row in leads if row.name), None),
            "has_cases": bool(intakes),
        },
        "nda": {
            "signed": nda is not None,
            "signed_at": _iso(nda.signed_at) if nda else None,
            "version": nda.document_version if nda else None,
            "signer_full_name": nda.signer_full_name if nda else None,
        },
        "cases": [{
            "id": str(row.id), "practice": row.practice.value,
            "category": row.category, "legal_area": row.legal_area.value,
            "description": row.description, "urgency": row.urgency.value,
            "deadline": row.deadline, "deadline_at": _iso(row.deadline_at),
            "status": row.status.value, "without_agreement": row.without_agreement,
            "created_at": _iso(row.created_at), "documents": documents.get(row.id, []),
        } for row in intakes],
        "agreements": [{
            "id": str(row.id), "intake_id": str(row.intake_id) if row.intake_id else None,
            "number": row.agreement_number, "revision": row.revision,
            "status": row.status.value, "subject": row.subject,
            "price_text": row.price_text, "amount_minor": row.amount_minor,
            "currency": row.currency, "client_details_complete": bool(
                (row.client_snapshot or {}).get("details_complete")
            ),
            "hash": row.document_hash, "version": row.document_version,
            "created_at": _iso(row.created_at), "sent_at": _iso(row.sent_at),
            "viewed_at": _iso(row.viewed_at), "signed_at": _iso(row.signed_at),
            "declined_at": _iso(row.declined_at),
            "messages": messages.get(row.id, []),
        } for row in agreements],
        "acts": [{
            "id": str(row.id), "agreement_id": str(row.agreement_id),
            "number": row.act_number, "status": row.status.value,
            "description": row.description_text, "amount_minor": row.amount_minor,
            "currency": row.currency, "hash": row.document_hash,
            "version": row.document_version, "created_at": _iso(row.created_at),
            "viewed_at": _iso(row.viewed_at), "accepted_at": _iso(row.accepted_at),
            "objected_at": _iso(row.objected_at), "objection_text": row.objection_text,
            "claimed_paid_at": _iso(row.claimed_paid_at), "paid_at": _iso(row.paid_at),
            "cancelled_at": _iso(row.cancelled_at), "cancel_reason": row.cancel_reason,
        } for row in acts],
    }
