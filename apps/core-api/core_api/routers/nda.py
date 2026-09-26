"""Подписание соглашения о конфиденциальности.

Подпись — нажатие кнопки в боте. Ценность имеет не сам факт, а зафиксированные
обстоятельства: кто, когда и какой именно текст видел. Поэтому вместе с
подписью сохраняются версия документа и контрольная сумма его текста.

Соглашение подписывается один раз на клиента и действует на все дальнейшие
обращения: повторное предложение подписать выглядело бы недоверием.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.client_notices import queue_notice
from core_api.client_principal import resolve
from core_api.config import get_settings
from core_api.db import get_db
from core_api.models import (
    ActorType,
    Lead,
    LegalIntake,
    NdaPersonalDataConsent,
    NdaSignature,
    Scope,
)
from core_api.nda_document import (
    NDA_VERSION,
    PDN_CONSENT_VERSION,
    document_hash,
    render_nda_text,
    render_pdn_consent_text,
)

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


def _assert_telegram_owner(lead: Lead, telegram_user_id: int | None) -> None:
    if telegram_user_id is None:
        return
    if lead.telegram_user_id != telegram_user_id:
        raise HTTPException(status_code=404, detail="Lead not found")


def _status_payload(db: Session, row: NdaSignature | None) -> dict:
    if row is None:
        return {"signed": False}
    consent = db.get(NdaPersonalDataConsent, row.pdn_consent_id) if row.pdn_consent_id else None
    return {
        "signed": True,
        "signed_at": row.signed_at.isoformat() if row.signed_at else None,
        "version": row.document_version,
        "current_version": NDA_VERSION,
        "signer_full_name": row.signer_full_name,
        "signer_contact": row.signer_contact,
        "signer_org": row.signer_org,
        "pdn_consent_accepted": consent is not None and consent.revoked_at is None,
        "pdn_consent_version": consent.document_version if consent else None,
        "pdn_consent_at": consent.accepted_at.isoformat() if consent and consent.accepted_at else None,
    }


def _signer_data(payload: dict) -> dict[str, str]:
    data = {
        "signer_full_name": str(payload.get("signer_full_name") or "").strip()[:255],
        "signer_contact": str(payload.get("signer_contact") or "").strip()[:255],
        "signer_identity_document": str(
            payload.get("signer_identity_document") or ""
        ).strip()[:500],
        "signer_org": str(payload.get("signer_org") or "").strip()[:500],
    }
    if not all(data[key] for key in (
        "signer_full_name", "signer_contact", "signer_identity_document"
    )):
        raise HTTPException(
            status_code=422,
            detail="signer_full_name, signer_contact and signer_identity_document are required",
        )
    return data


def _operator_data() -> tuple[str, str, str]:
    settings = get_settings()
    return (
        getattr(settings, "operator_name", "") or "Исполнитель",
        getattr(settings, "operator_inn", ""),
        getattr(settings, "privacy_contact_email", ""),
    )


def _render_nda(data: dict[str, str]) -> str:
    operator_name, operator_inn, _ = _operator_data()
    return render_nda_text(operator_name, operator_inn, **data)


def _render_consent(data: dict[str, str]) -> str:
    operator_name, operator_inn, privacy_email = _operator_data()
    return render_pdn_consent_text(
        operator_name,
        operator_inn,
        privacy_contact_email=privacy_email,
        **data,
    )


def _lead_from_payload(db: Session, payload: dict) -> Lead:
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
    return lead


def _telegram_user_id(payload: dict, lead: Lead) -> int | None:
    telegram_user_id = payload.get("telegram_user_id")
    if telegram_user_id is None:
        return None
    try:
        telegram_user_id = int(telegram_user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="telegram_user_id must be an integer") from exc
    if lead.telegram_user_id != telegram_user_id:
        raise HTTPException(status_code=403, detail="Telegram user does not own this lead")
    return telegram_user_id


@dataclass(frozen=True)
class _Signer:
    """Кто действует: Telegram ID или учётная запись (вход через Яндекс ID)."""

    telegram_user_id: int | None
    account_id: uuid.UUID | None = None
    email: str | None = None


def _client_owner(db: Session, payload: dict, lead: Lead) -> _Signer:
    """Лид принадлежит тому, кто действует: по учётной записи — если лид среди
    её дел (client_principal), иначе — по Telegram, как раньше."""
    raw_account = payload.get("client_account_id")
    if raw_account:
        try:
            account_id = uuid.UUID(str(raw_account))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="client_account_id must be a UUID") from exc
        principal = resolve(db, client_account_id=account_id)
        if lead.id not in principal.lead_ids:
            raise HTTPException(status_code=403, detail="Client account does not own this lead")
        return _Signer(principal.telegram_user_id, account_id, principal.email)
    return _Signer(_telegram_user_id(payload, lead))


def _consent_from_payload(
    db: Session, payload: dict, lead: Lead, signer: _Signer
) -> NdaPersonalDataConsent:
    try:
        consent_id = uuid.UUID(str(payload.get("pdn_consent_id") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="pdn_consent_id is required") from exc
    consent = db.get(NdaPersonalDataConsent, consent_id)
    if consent is None or consent.lead_id != lead.id or consent.revoked_at is not None:
        raise HTTPException(status_code=422, detail="valid personal data consent is required")
    if signer.account_id is not None:
        if consent.signer_account_id != signer.account_id:
            raise HTTPException(status_code=403, detail="Consent belongs to another client")
    elif signer.telegram_user_id is not None and consent.telegram_user_id != signer.telegram_user_id:
        raise HTTPException(status_code=403, detail="Consent belongs to another Telegram user")
    return consent


def _intake_id_for_lead(db: Session, lead_id: uuid.UUID) -> str | None:
    intake_id = db.execute(
        select(LegalIntake.id).where(LegalIntake.lead_id == lead_id)
        .order_by(LegalIntake.created_at.desc(), LegalIntake.id.desc()).limit(1)
    ).scalar_one_or_none()
    return str(intake_id) if intake_id else None


@router.get("/document")
def get_nda_document(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
) -> dict:
    """Актуальный текст соглашения с версией и контрольной суммой."""
    _ = identity
    operator_name, operator_inn, _ = _operator_data()
    text = render_nda_text(operator_name, operator_inn)
    return {
        "version": NDA_VERSION,
        "text": text,
        "hash": document_hash(text),
    }


@router.post("/personal-data-consent/preview")
def preview_personal_data_consent(
    payload: dict,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
) -> dict:
    """Точный текст отдельного согласия с введёнными клиентом данными."""
    _ = identity
    text = _render_consent(_signer_data(payload))
    return {"version": PDN_CONSENT_VERSION, "text": text, "hash": document_hash(text)}


@router.post("/personal-data-consent/accept", status_code=status.HTTP_201_CREATED)
def accept_personal_data_consent(
    payload: dict,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Фиксирует отдельное от NDA согласие на обработку данных."""
    lead = _lead_from_payload(db, payload)
    signer = _client_owner(db, payload, lead)
    data = _signer_data(payload)
    if payload.get("pdn_consent_accepted") is not True:
        raise HTTPException(status_code=422, detail="personal data consent is required")

    text = _render_consent(data)
    current_hash = document_hash(text)
    if str(payload.get("document_hash") or "").strip().lower() != current_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="consent changed since it was shown to the signer",
        )

    existing = db.scalar(
        select(NdaPersonalDataConsent)
        .where(
            NdaPersonalDataConsent.lead_id == lead.id,
            NdaPersonalDataConsent.document_hash == current_hash,
            NdaPersonalDataConsent.revoked_at.is_(None),
        )
        .order_by(NdaPersonalDataConsent.accepted_at.desc())
        .limit(1)
    )
    if existing is not None:
        return {
            "accepted": True,
            "already_accepted": True,
            "consent_id": str(existing.id),
            "accepted_at": existing.accepted_at.isoformat() if existing.accepted_at else None,
            "version": existing.document_version,
        }

    row = NdaPersonalDataConsent(
        lead_id=lead.id,
        accepted_at=datetime.now(timezone.utc),
        telegram_user_id=signer.telegram_user_id or lead.telegram_user_id,
        signer_account_id=signer.account_id,
        signer_email=signer.email,
        telegram_username=str(payload.get("telegram_username") or "")[:255] or None,
        signer_full_name=data["signer_full_name"],
        signer_contact=data["signer_contact"],
        signer_org=data["signer_org"] or None,
        signer_identity_document=data["signer_identity_document"],
        document_version=PDN_CONSENT_VERSION,
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
        action="nda.pdn_consent.accept",
        target_type="lead",
        target_id=lead.id,
        details={"version": PDN_CONSENT_VERSION, "channel": row.channel},
    )
    db.commit()
    return {
        "accepted": True,
        "already_accepted": False,
        "consent_id": str(row.id),
        "accepted_at": row.accepted_at.isoformat(),
        "version": row.document_version,
    }


@router.post("/document/preview")
def preview_nda_document(
    payload: dict,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Персонализированная редакция NDA после отдельного согласия."""
    _ = identity
    lead = _lead_from_payload(db, payload)
    signer = _client_owner(db, payload, lead)
    consent = _consent_from_payload(db, payload, lead, signer)
    data = {
        "signer_full_name": consent.signer_full_name,
        "signer_contact": consent.signer_contact,
        "signer_identity_document": consent.signer_identity_document,
        "signer_org": consent.signer_org or "",
    }
    text = _render_nda(data)
    return {"version": NDA_VERSION, "text": text, "hash": document_hash(text)}


@router.get("/status/{lead_id}")
def get_nda_status(
    lead_id: uuid.UUID,
    telegram_user_id: int | None = Query(default=None, gt=0),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Подписано ли соглашение этим клиентом."""
    _ = identity
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    _assert_telegram_owner(lead, telegram_user_id)
    return _status_payload(db, _signature_for_lead(db, lead))


@router.get("/by-telegram/{telegram_user_id}")
def get_nda_context_by_telegram(
    telegram_user_id: int,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Возвращает актуальное обращение клиента без зависимости от SQLite бота."""
    _ = identity
    lead = db.execute(
        select(Lead)
        .where(Lead.telegram_user_id == telegram_user_id)
        .order_by(Lead.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"lead_id": str(lead.id), **_status_payload(db, _signature_for_lead(db, lead))}


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
    lead = _lead_from_payload(db, payload)
    lead_id = lead.id
    signer = _client_owner(db, payload, lead)

    existing = _signature_for_lead(db, lead)
    if existing is not None:
        return {
            "signed": True,
            "already_signed": True,
            "signed_at": existing.signed_at.isoformat() if existing.signed_at else None,
            "version": existing.document_version,
            "pdn_consent_accepted": existing.pdn_consent_id is not None,
            "intake_id": _intake_id_for_lead(db, lead.id),
        }

    consent = _consent_from_payload(db, payload, lead, signer)
    data = {
        "signer_full_name": consent.signer_full_name,
        "signer_contact": consent.signer_contact,
        "signer_identity_document": consent.signer_identity_document,
        "signer_org": consent.signer_org or "",
    }
    text = _render_nda(data)
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

    row = NdaSignature(
        lead_id=lead_id,
        telegram_user_id=signer.telegram_user_id or lead.telegram_user_id,
        signer_account_id=signer.account_id,
        signer_email=signer.email,
        telegram_username=str(payload.get("telegram_username") or "")[:255] or None,
        signer_name=str(payload.get("signer_name") or lead.name or "")[:255] or None,
        signer_full_name=consent.signer_full_name,
        signer_contact=consent.signer_contact,
        signer_org=consent.signer_org,
        signer_identity_document=consent.signer_identity_document,
        pdn_consent_id=consent.id,
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
        details={
            "version": NDA_VERSION,
            "pdn_consent_version": consent.document_version,
            "channel": row.channel,
        },
    )
    if row.channel == "miniapp":
        queue_notice(
            db,
            f"nda:{row.id}:signed",
            f"Клиент {row.signer_full_name} подписал NDA в кабинете.",
        )
    db.commit()
    db.refresh(row)

    return {
        "signed": True,
        "already_signed": False,
        "signed_at": row.signed_at.isoformat() if row.signed_at else None,
        "version": row.document_version,
        "pdn_consent_version": consent.document_version,
        "intake_id": _intake_id_for_lead(db, lead.id),
    }
