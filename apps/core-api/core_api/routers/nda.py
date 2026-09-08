"""Подписание соглашения о конфиденциальности.

Подпись — нажатие кнопки в боте. Ценность имеет не сам факт, а зафиксированные
обстоятельства: кто, когда и какой именно текст видел. Поэтому вместе с
подписью сохраняются версия документа и контрольная сумма его текста.

Соглашение подписывается один раз на клиента и действует на все дальнейшие
обращения: повторное предложение подписать выглядело бы недоверием.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.config import get_settings
from core_api.db import get_db
from core_api.models import ActorType, Lead, NdaSignature, Scope
from core_api.nda_document import NDA_VERSION, document_hash, render_nda_text

router = APIRouter(prefix="/api/v1/nda", tags=["nda"])


def _signature_for_lead(db: Session, lead: Lead) -> NdaSignature | None:
    checks = [NdaSignature.lead_id == lead.id]
    if lead.telegram_user_id is not None:
        checks.append(NdaSignature.telegram_user_id == lead.telegram_user_id)
    return db.execute(
        select(NdaSignature)
        .where(or_(*checks))
        .order_by(NdaSignature.signed_at.desc())
        .limit(1)
    ).scalar_one_or_none()


@router.get("/document")
def get_nda_document(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
) -> dict:
    """Актуальный текст соглашения с версией и контрольной суммой."""
    _ = identity
    settings = get_settings()
    text = render_nda_text(getattr(settings, "operator_name", "") or "Исполнитель")
    return {"version": NDA_VERSION, "text": text, "hash": document_hash(text)}


@router.get("/status/{lead_id}")
def get_nda_status(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Подписано ли соглашение этим клиентом."""
    _ = identity
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    row = _signature_for_lead(db, lead)
    if row is None:
        return {"signed": False}
    return {
        "signed": True,
        "signed_at": row.signed_at.isoformat() if row.signed_at else None,
        "version": row.document_version,
        "current_version": NDA_VERSION,
        "signer_full_name": row.signer_full_name,
        "signer_contact": row.signer_contact,
        "signer_org": row.signer_org,
    }


@router.post("/sign", status_code=status.HTTP_201_CREATED)
def sign_nda(
    payload: dict,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Фиксирует подписание соглашения клиентом.

    Повторное подписание не создаёт новую запись: соглашение действует на все
    обращения клиента, и вторая подпись означала бы, что первая чем-то плоха.
    """
    lead_id_raw = str(payload.get("lead_id") or "").strip()
    if not lead_id_raw:
        raise HTTPException(status_code=400, detail="lead_id is required")
    try:
        lead_id = uuid.UUID(lead_id_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="lead_id must be a UUID") from exc

    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    existing = _signature_for_lead(db, lead)
    if existing is not None:
        return {
            "signed": True,
            "already_signed": True,
            "signed_at": existing.signed_at.isoformat() if existing.signed_at else None,
            "version": existing.document_version,
        }

    settings = get_settings()
    text = render_nda_text(getattr(settings, "operator_name", "") or "Исполнитель")
    current_hash = document_hash(text)

    # Клиент присылает контрольную сумму текста, который был у него на экране.
    # Если она разошлась с текущей — между показом и нажатием кнопки успела
    # выйти новая редакция, и человек подписывает не то, что читал.
    #
    # Записать здесь текущий хеш было бы хуже, чем отказать: в базе осталась бы
    # достоверная на вид запись о подписании документа, которого подписант не
    # видел. Поэтому отказываем и просим показать текст заново.
    seen_hash = str(payload.get("document_hash") or "").strip().lower()
    if not seen_hash:
        raise HTTPException(status_code=422, detail="document_hash is required")
    if seen_hash != current_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="document changed since it was shown to the signer",
        )

    # Данные подписанта обязательны: подпись, за которой стоит только
    # идентификатор аккаунта, при споре почти ничего не доказывает.
    full_name = str(payload.get("signer_full_name") or "").strip()
    contact = str(payload.get("signer_contact") or "").strip()
    if not full_name or not contact:
        raise HTTPException(
            status_code=422,
            detail="signer_full_name and signer_contact are required",
        )

    row = NdaSignature(
        lead_id=lead_id,
        telegram_user_id=payload.get("telegram_user_id") or lead.telegram_user_id,
        telegram_username=str(payload.get("telegram_username") or "")[:255] or None,
        signer_name=str(payload.get("signer_name") or lead.name or "")[:255] or None,
        signer_full_name=full_name[:255],
        signer_contact=contact[:255],
        signer_org=(str(payload.get("signer_org") or "").strip()[:500] or None),
        document_version=NDA_VERSION,
        document_hash=current_hash,
        document_text=text,
        channel=str(payload.get("channel") or "telegram_bot")[:32],
    )
    db.add(row)
    db.flush()

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="nda.sign",
        target_type="lead",
        target_id=lead_id,
        details={"version": NDA_VERSION, "channel": row.channel},
    )
    db.commit()
    db.refresh(row)

    return {
        "signed": True,
        "already_signed": False,
        "signed_at": row.signed_at.isoformat() if row.signed_at else None,
        "version": row.document_version,
    }
