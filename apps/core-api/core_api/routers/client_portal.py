from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import (
    ActorType,
    IntakeDocument,
    Lead,
    LegalIntake,
    NdaPersonalDataConsent,
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


def _normalize_contact(value: str) -> str:
    """Телефон в любом формате (+7/8/пробелы/дефисы) сводим к последним 10
    цифрам — иначе "+7 909 233-09-09" и "89092330909" не совпадут при
    буквальном сравнении. Email — просто lower+strip."""
    stripped = value.strip().lower()
    digits = "".join(ch for ch in stripped if ch.isdigit())
    if "@" not in stripped and len(digits) >= 10:
        return digits[-10:]
    return stripped


class VerifyReturningClientRequest(BaseModel):
    contact: str = Field(min_length=3, max_length=255)
    agreement_number: str = Field(min_length=1, max_length=64)


@router.post("/verify")
def verify_returning_client(
    payload: VerifyReturningClientRequest,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Веб-ассистент (анонимный посетитель сайта) заявляет, что уже клиент, и
    называет контакт + номер договора. Проверяем ОБА, а не только контакт —
    голого совпадения по телефону/email недостаточно (посторонний мог его
    узнать), а номер договора — то, что знает только реальная сторона.

    Лидам без договора (только обращение) это не помогает — намеренно:
    у LegalIntake нет пользовательского номера для надёжной сверки, а
    approximate-match по описанию задачи — слишком слабая защита.
    """
    _ = identity
    agreement = db.scalar(
        select(ServiceAgreement).where(
            ServiceAgreement.agreement_number == payload.agreement_number.strip()
        )
    )
    if agreement is None or agreement.client_telegram_user_id is None:
        return {"verified": False}

    telegram_user_id = agreement.client_telegram_user_id
    leads = db.scalars(
        select(Lead).where(Lead.telegram_user_id == telegram_user_id)
    ).all()
    normalized_input = _normalize_contact(payload.contact)
    known_contacts = {
        _normalize_contact(value)
        for lead in leads
        for value in (lead.phone, lead.email, lead.contact)
        if value
    }
    if normalized_input not in known_contacts:
        return {"verified": False}

    return {"verified": True, "telegram_user_id": telegram_user_id}


def _normalize_phone(value: str | None) -> str | None:
    """Оставляет "+" и цифры; отбрасывает то, что после нормализации короче
    10 цифр — обрывок номера хуже, чем пустое поле."""
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) < 10:
        return None
    return f"+{digits}"


class TelegramProfileSyncRequest(BaseModel):
    telegram_user_id: int = Field(gt=0)
    phone: str | None = Field(default=None, max_length=32)
    phone_verified: bool = False


@router.post("/telegram-profile")
def sync_telegram_profile(
    payload: TelegramProfileSyncRequest,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Клиент вошёл в личный кабинет на сайте через Telegram Login со scope
    phone и дал согласие — Telegram отдал верифицированный номер. Дозаполняем
    им ТОЛЬКО пустой Lead.phone (никогда не перезаписываем то, что уже есть:
    источник в базе может быть точнее — например, номер, продиктованный
    голосом юристу и уточнённый вручную).

    Непроверенный или отсутствующий номер — no-op, идемпотентно: повторный
    вызов с уже заполненными лидами просто вернёт leads_updated=0.
    """
    leads = db.scalars(
        select(Lead).where(Lead.telegram_user_id == payload.telegram_user_id)
    ).all()
    phone = _normalize_phone(payload.phone) if payload.phone_verified else None
    updated_ids: list = []
    if phone:
        for lead in leads:
            if not (lead.phone or "").strip():
                lead.phone = phone
                updated_ids.append(lead.id)
    if updated_ids:
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="lead.phone_from_telegram",
            target_type="lead",
            target_id=updated_ids[0],
            details={"leads_updated": len(updated_ids), "telegram_user_id": payload.telegram_user_id},
        )
        db.commit()
    return {
        "telegram_user_id": payload.telegram_user_id,
        "leads_matched": len(leads),
        "leads_updated": len(updated_ids),
    }


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
    nda_consent = (
        db.get(NdaPersonalDataConsent, nda.pdn_consent_id)
        if nda and nda.pdn_consent_id
        else None
    )
    return {
        "client": {
            "lead_id": str(leads[0].id) if leads else None,
            "name": next((row.name for row in leads if row.name), None),
            "phone": next((row.phone for row in leads if row.phone), None),
            "has_cases": bool(intakes),
        },
        "nda": {
            "signed": nda is not None,
            "signed_at": _iso(nda.signed_at) if nda else None,
            "version": nda.document_version if nda else None,
            "signer_full_name": nda.signer_full_name if nda else None,
            "pdn_consent_at": _iso(nda_consent.accepted_at) if nda_consent else None,
            "pdn_consent_version": nda_consent.document_version if nda_consent else None,
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
            "kind": "supplement" if row.parent_agreement_id else "agreement",
            "parent_agreement_id": str(row.parent_agreement_id) if row.parent_agreement_id else None,
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
            "number": row.act_number, "status": row.status.value, "kind": row.kind or "act",
            "description": row.description_text, "amount_minor": row.amount_minor,
            "currency": row.currency, "hash": row.document_hash,
            "version": row.document_version, "created_at": _iso(row.created_at),
            "viewed_at": _iso(row.viewed_at), "accepted_at": _iso(row.accepted_at),
            "objected_at": _iso(row.objected_at), "objection_text": row.objection_text,
            "claimed_paid_at": _iso(row.claimed_paid_at), "paid_at": _iso(row.paid_at),
            "cancelled_at": _iso(row.cancelled_at), "cancel_reason": row.cancel_reason,
        } for row in acts],
    }
