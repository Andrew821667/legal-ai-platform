"""Запрос документов у клиента — рабочее место юриста (см. core_api.document_requests)."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core_api import document_requests
from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import ActorType, DocumentRequest, IntakeDocument, Lead, LegalIntake, Scope

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


class RequestIn(BaseModel):
    titles: list[str] = Field(min_length=1, max_length=document_requests.MAX_ITEMS)
    note: str | None = Field(default=None, max_length=1000)


class StatusIn(BaseModel):
    status: Literal["open", "received", "cancelled"]
    # Каким файлом получен — если юрист связывает пункт с уже присланным.
    document_id: uuid.UUID | None = None


@router.post("/intakes/{intake_id}/document-requests")
def request_documents(
    intake_id: uuid.UUID,
    body: RequestIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Сохранить список и сказать клиенту: в Telegram или — без него — через кабинет."""
    intake = db.get(LegalIntake, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="Legal intake not found")
    lead = db.get(Lead, intake.lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    created = document_requests.create(db, intake, body.titles, body.note)
    if not created:
        raise HTTPException(status_code=409, detail="These documents are already requested")
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="legal_intake.document_request",
        target_type="legal_intake",
        target_id=intake.id,
        details={"count": len(created)},
    )
    db.commit()
    # Сообщение — после записи: список уже виден в кабинете, даже если
    # Telegram сейчас недоступен.
    delivery = document_requests.notify(lead, [row.title for row in created], body.note)
    return {
        "requests": [document_requests.payload(row) for row in created],
        **delivery,
    }


@router.patch("/document-requests/{request_id}")
def set_request_status(
    request_id: uuid.UUID,
    body: StatusIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Юрист отмечает: получен (например, прислан в чат), не нужен или снова ждём."""
    row = db.get(DocumentRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document request not found")
    if body.document_id is not None:
        document = db.get(IntakeDocument, body.document_id)
        if document is None or document.intake_id != row.intake_id:
            raise HTTPException(status_code=404, detail="Document not found")
    document_requests.mark(row, body.status, body.document_id)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="legal_intake.document_request_status",
        target_type="legal_intake",
        target_id=row.intake_id,
        details={"request_id": str(row.id), "status": body.status},
    )
    db.commit()
    return document_requests.payload(row)
