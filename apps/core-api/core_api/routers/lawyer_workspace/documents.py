"""Тексты документов для просмотра юристом: договор, NDA, согласие, файл клиента."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import (
    IntakeDocument,
    LegalIntake,
    NdaPersonalDataConsent,
    NdaSignature,
    Scope,
    ServiceAgreement,
)
from core_api.routers.lawyer_workspace.common import (
    _iso,
)

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


@router.get("/agreements/{agreement_id}/document")
def agreement_document(
    agreement_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Точный текст, который видел и подписывал клиент, и его хеш.

    Карточка показывает условия по полям — это реконструкция. При споре о
    содержании нужна не она, а сам документ: хеш здесь и есть то, под чем
    клиент поставил подпись, и без текста рядом он ничего не доказывает.
    Отдаётся отдельно: текст длинный, а нужен редко.
    """
    _ = identity
    item = db.get(ServiceAgreement, agreement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
    return {
        "agreement_id": str(item.id),
        "number": item.agreement_number,
        "document_version": item.document_version,
        "document_hash": item.document_hash,
        "document_text": item.document_text,
    }


@router.get("/nda/{nda_id}/document")
def nda_document(
    nda_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """То же для соглашения о конфиденциальности."""
    _ = identity
    item = db.get(NdaSignature, nda_id)
    if item is None:
        raise HTTPException(status_code=404, detail="NDA not found")
    return {
        "nda_id": str(item.id),
        "document_version": item.document_version,
        "document_hash": item.document_hash,
        "document_text": item.document_text,
    }


@router.get("/nda-consents/{consent_id}/document")
def nda_consent_document(
    consent_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Точный отдельный текст согласия на обработку персональных данных."""
    _ = identity
    item = db.get(NdaPersonalDataConsent, consent_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Consent not found")
    return {
        "consent_id": str(item.id),
        "document_version": item.document_version,
        "document_hash": item.document_hash,
        "document_text": item.document_text,
        "accepted_at": _iso(item.accepted_at),
        "revoked_at": _iso(item.revoked_at),
    }


@router.get("/documents/{document_id}")
def document_meta(
    document_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Где лежит присланный клиентом файл.

    Сам файл живёт в Telegram: здесь хранится только его идентификатор, а
    достать байты может лишь бот своим токеном. Веб-слой берёт отсюда
    идентификатор по номеру документа, а не принимает его от браузера: так
    файл можно получить только для документа, который есть в базе.
    """
    _ = identity
    row = db.get(IntakeDocument, document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    intake = db.get(LegalIntake, row.intake_id)
    return {
        "document_id": str(row.id),
        "intake_id": str(row.intake_id),
        "lead_id": str(intake.lead_id) if intake else None,
        "telegram_file_id": row.telegram_file_id,
        "file_name": row.file_name,
        "file_size": row.file_size,
        "mime_type": row.mime_type,
        "created_at": _iso(row.created_at),
    }
