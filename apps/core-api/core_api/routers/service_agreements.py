"""Двусторонний договор юридических услуг в Telegram."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.client_notices import queue_notice
from core_api.client_proposal import (
    STATUS_LABELS,
    build_proposal_markup,
    build_proposal_text,
    build_reply_text,
    build_summary,
)
from core_api.client_principal import ClientRef, Principal, resolve
from core_api.config import get_settings
from core_api.db import get_db
from core_api.idempotency import cached_response, store_response
from core_api import telegram_delivery
from core_api.lead_notifications import _post_telegram_message
from core_api.models import (
    TEMPLATE_KIND_BY_PRACTICE,
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
    conflict_check_blocks_agreement,
    nda_required_for_agreement,
)
from core_api.service_agreement import (
    SUPPLEMENT_VERSION,
    agreement_version,
    document_hash,
    render_agreement_text,
    render_supplement_text,
)

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
    # Копейки. Необязательно: мастер в боте пока спрашивает только текст.
    amount_minor: int | None = Field(default=None, ge=0, le=10**13)
    payment_terms: str = Field(min_length=2, max_length=2000)
    expires_in_days: int = Field(default=7, ge=1, le=30)


class SupplementCreate(BaseModel):
    """Допсоглашение: новая общая стоимость и дополнительные работы."""

    prepared_by_telegram_user_id: int = Field(gt=0)
    scope_text: str = Field(min_length=10, max_length=6000)
    schedule_text: str | None = Field(default=None, max_length=2000)
    price_text: str = Field(min_length=2, max_length=500)
    # Новая общая стоимость по договору — после подписи она же становится
    # учётной суммой основного договора. Без числа допсоглашение не нужно.
    amount_minor: int = Field(ge=0, le=10**13)
    payment_terms: str | None = Field(default=None, max_length=2000)
    expires_in_days: int = Field(default=7, ge=1, le=30)


class DeliveryData(BaseModel):
    chat_id: int
    message_id: int
    telegram_user_id: int = Field(gt=0)
    callback_id: str = Field(min_length=1, max_length=255)


class ClientAction(ClientRef):
    document_hash: str = Field(min_length=64, max_length=64)
    message_id: int | None = None
    callback_id: str = Field(min_length=1, max_length=255)
    channel: Literal["telegram_bot", "miniapp"] = "telegram_bot"


class AgreementSign(ClientAction):
    telegram_username: str | None = Field(default=None, max_length=255)
    signer_position: str | None = Field(default=None, max_length=255)
    authority_basis: str | None = Field(default=None, max_length=500)


class AgreementDecline(ClientRef):
    reason: str | None = Field(default=None, max_length=1000)
    callback_id: str = Field(min_length=1, max_length=255)
    channel: Literal["telegram_bot", "miniapp"] = "telegram_bot"


class AgreementClientDetails(ClientRef):
    client_type: Literal["person", "organization"]
    full_name: str = Field(min_length=5, max_length=255)
    contact: str = Field(min_length=3, max_length=255)
    address: str = Field(min_length=5, max_length=500)
    identity_document: str | None = Field(default=None, min_length=5, max_length=500)
    org_name: str | None = Field(default=None, min_length=3, max_length=500)
    inn: str | None = Field(default=None, max_length=12)
    ogrn: str | None = Field(default=None, max_length=15)
    position: str | None = Field(default=None, min_length=2, max_length=255)
    authority_basis: str | None = Field(default=None, min_length=2, max_length=500)
    channel: Literal["telegram_bot", "miniapp"] = "telegram_bot"

    @model_validator(mode="after")
    def validate_party_details(self) -> AgreementClientDetails:
        fields = (
            "full_name",
            "contact",
            "address",
            "identity_document",
            "org_name",
            "inn",
            "ogrn",
            "position",
            "authority_basis",
        )
        for name in fields:
            if isinstance(value := getattr(self, name), str):
                setattr(self, name, value.strip())
        if not all((self.full_name, self.contact, self.address)):
            raise ValueError("client details are incomplete")
        if self.client_type == "person" and not self.identity_document:
            raise ValueError("identity_document is required for a person")
        if self.client_type == "organization":
            required = (self.org_name, self.inn, self.ogrn, self.position, self.authority_basis)
            if not all(required):
                raise ValueError("organization details are incomplete")
            if not self.inn.isdigit() or len(self.inn) not in {10, 12}:
                raise ValueError("inn must contain 10 or 12 digits")
            if not self.ogrn.isdigit() or len(self.ogrn) not in {13, 15}:
                raise ValueError("ogrn must contain 13 or 15 digits")
        return self


class AgreementMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    telegram_user_id: int | None = None
    client_account_id: uuid.UUID | None = None
    channel: Literal["telegram_bot", "miniapp"] = "telegram_bot"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Даты в тексте допсоглашения — по Москве, как и у практики: подпись в час
# ночи не должна датироваться вчерашним днём.
_DOCUMENT_TZ = ZoneInfo("Europe/Moscow")


def _is_supplement(item: ServiceAgreement) -> bool:
    return item.parent_agreement_id is not None


def _document_title(item: ServiceAgreement) -> str:
    return "Дополнительное соглашение" if _is_supplement(item) else "Договор"


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


def _assert_client(
    db: Session,
    item: ServiceAgreement,
    telegram_user_id: int | None = None,
    client_account_id: uuid.UUID | None = None,
) -> Principal:
    """Клиент — владелец документа: по Telegram или по учётной записи (client_principal)."""
    principal = resolve(db, telegram_user_id=telegram_user_id, client_account_id=client_account_id)
    if not principal.owns(lead_id=item.lead_id, client_telegram_user_id=item.client_telegram_user_id):
        raise HTTPException(status_code=403, detail="Agreement belongs to another client")
    return principal


def _client_details_text(client: dict) -> str:
    if client.get("client_type") == "organization":
        return "; ".join(
            (
                f"ИНН {client['inn']}",
                f"ОГРН {client['ogrn']}",
                f"адрес: {client['address']}",
                f"представитель: {client['full_name']}",
                f"должность: {client['position']}",
                f"основание полномочий: {client['authority_basis']}",
                f"контакт: {client['contact']}",
            )
        )
    return "; ".join(
        (
            f"документ, удостоверяющий личность: {client['identity_document']}",
            f"адрес: {client['address']}",
            f"контакт: {client['contact']}",
        )
    )


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
        "amount_minor": item.amount_minor,
        "currency": item.currency,
        "payment_terms": item.payment_terms,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "sent_at": item.sent_at.isoformat() if item.sent_at else None,
        "viewed_at": item.viewed_at.isoformat() if item.viewed_at else None,
        "signed_at": item.signed_at.isoformat() if item.signed_at else None,
        "declined_at": item.declined_at.isoformat() if item.declined_at else None,
        "reminders_sent": item.reminders_sent or 0,
        "last_reminded_at": item.last_reminded_at.isoformat() if item.last_reminded_at else None,
        "client_telegram_user_id": item.client_telegram_user_id,
        "client_name": client.get("full_name"),
        "client_contact": client.get("contact"),
        "client_org": client.get("org"),
        "client_type": client.get("client_type"),
        "client_details_complete": bool(client.get("details_complete")),
        "client_position": client.get("position"),
        "client_authority_basis": client.get("authority_basis"),
        "signer_position": item.signer_position,
        "authority_basis": item.authority_basis,
        "version": item.document_version,
        "hash": item.document_hash,
        "template_kind": item.template_kind.value,
        # Допсоглашение идёт тем же путём, что и договор; по этим полям бот и
        # кабинет называют его своим именем, а не «договором».
        "kind": "supplement" if _is_supplement(item) else "agreement",
        "document_title": _document_title(item),
        "parent_agreement_id": str(item.parent_agreement_id) if item.parent_agreement_id else None,
    }
    # Готовое сообщение клиенту собирается здесь, а не у каждого отправителя.
    # Бот берёт его отсюда, рабочее место — тоже: одна формулировка на всех.
    data["proposal_text"] = build_proposal_text(data)
    data["summary_text"] = build_summary(data)
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
    # Проверка конфликта интересов — условие договора там, где есть право:
    # в чисто инженерной практике она остаётся пометкой, а не воротами.
    if conflict_check_blocks_agreement(intake.practice) and intake.conflict_status.value != "clear":
        raise HTTPException(status_code=409, detail="Conflict check must be clear")

    lead = db.get(Lead, intake.lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.telegram_user_id is None:
        raise HTTPException(status_code=409, detail="Client has no Telegram dialog")
    nda = _nda_for_lead(db, lead)
    # NDA подтверждает личность и фиксирует режим материалов до договора.
    # Поэтому он обязателен для любой практики платформы.
    if nda is None and nda_required_for_agreement(intake.practice):
        raise HTTPException(status_code=409, detail="NDA must be signed first")
    template_kind = TEMPLATE_KIND_BY_PRACTICE[intake.practice]

    previous = db.execute(
        select(ServiceAgreement)
        .where(ServiceAgreement.intake_id == intake.id)
        .where(ServiceAgreement.parent_agreement_id.is_(None))
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
        "full_name": (nda.signer_full_name if nda else None) or lead.name or "Заказчик",
        "contact": (nda.signer_contact if nda else None) or lead.contact or "",
        "org": (nda.signer_org if nda else None) or lead.company,
        "details_complete": False,
        "nda_id": str(nda.id) if nda else None,
        "nda_version": nda.document_version if nda else None,
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
        client_details="",
        subject=payload.subject,
        scope=payload.scope_text,
        exclusions=payload.exclusions_text,
        schedule=payload.schedule_text,
        price=payload.price_text,
        payment_terms=payload.payment_terms,
        template_kind=template_kind.value,
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
        amount_minor=payload.amount_minor,
        payment_terms=payload.payment_terms.strip(),
        created_by=identity.name,
        prepared_by_telegram_user_id=payload.prepared_by_telegram_user_id,
        operator_snapshot=operator,
        client_snapshot=client,
        template_kind=template_kind,
        document_text=text,
        document_version=agreement_version(template_kind.value),
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


def _apply_supplement(db: Session, identity: ApiKeyIdentity, item: ServiceAgreement) -> None:
    """Подписанное допсоглашение меняет учётную сумму основного договора.

    Текст договора, под которым стоит подпись, не трогаем: новая стоимость
    живёт в тексте допсоглашения, а в итоги идёт как сумма договора.
    """
    parent = db.execute(
        select(ServiceAgreement)
        .where(ServiceAgreement.id == item.parent_agreement_id)
        .with_for_update()
    ).scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=409, detail="Main agreement not found")
    before = parent.amount_minor
    parent.amount_minor = item.amount_minor
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="service_agreement.amount",
        target_type="service_agreement",
        target_id=parent.id,
        details={
            "from": before,
            "to": item.amount_minor,
            "supplement_id": str(item.id),
            "supplement_number": item.agreement_number,
        },
    )


@router.post("/{agreement_id}/supplements", status_code=status.HTTP_201_CREATED, response_model=None)
def create_supplement(
    agreement_id: uuid.UUID,
    payload: SupplementCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """Дополнительное соглашение к подписанному договору — черновиком.

    Сумму подписанного договора нельзя поменять в одну сторону: клиент
    подписывал другую. Новая общая стоимость и дополнительные работы уходят
    ему документом, и только его подпись переносит сумму в договор.

    Неподписанное допсоглашение к тому же договору заменяется новым — как
    редакция договора: у клиента на руках должна быть одна актуальная.
    """
    namespace = "service_agreements.supplement"
    if idempotency_key and (cached := cached_response(db, idempotency_key, namespace=namespace)):
        code, body = cached
        return JSONResponse(status_code=code, content=body)

    parent = _get(db, agreement_id, lock=True)
    if _is_supplement(parent):
        raise HTTPException(status_code=409, detail="A supplement is added to the main agreement")
    if parent.status != ServiceAgreementStatus.signed:
        raise HTTPException(
            status_code=409,
            detail="Only a signed agreement takes a supplement; change an unsigned one with a new revision",
        )
    if not parent.client_telegram_user_id:
        raise HTTPException(status_code=409, detail="Client has no Telegram")

    supplements = db.execute(
        select(ServiceAgreement)
        .where(ServiceAgreement.parent_agreement_id == parent.id)
        .order_by(ServiceAgreement.created_at.desc())
        .with_for_update()
    ).scalars().all()
    # Номер растёт только с подписью: отклонённое или заменённое допсоглашение
    # не занимает номер, новое выходит под тем же номером следующей редакцией.
    supplement_no = 1 + sum(1 for row in supplements if row.status == ServiceAgreementStatus.signed)
    base = parent.agreement_number.split("-R", 1)[0]
    series = f"{base}-DS{supplement_no}"
    same_series = [row for row in supplements if row.agreement_number.split("-R", 1)[0] == series]
    revision = 1 + max((row.revision for row in same_series), default=0)
    number = f"{series}-R{revision}" if revision > 1 else series
    for row in supplements:
        if row.status in _OPEN:
            row.status = ServiceAgreementStatus.superseded
    previous = same_series[0] if same_series else None

    client = dict(parent.client_snapshot or {})
    operator = parent.operator_snapshot or {}
    created = _now()
    expires = created + timedelta(days=payload.expires_in_days)
    signed_on = (parent.signed_at or created).astimezone(_DOCUMENT_TZ)
    scope = payload.scope_text.strip()
    schedule = (payload.schedule_text or "").strip()
    payment_terms = (payload.payment_terms or "").strip()
    text = render_supplement_text(
        number=number,
        supplement_no=supplement_no,
        parent_number=parent.agreement_number,
        parent_date=signed_on.strftime("%d.%m.%Y"),
        created_date=created.astimezone(_DOCUMENT_TZ).strftime("%d.%m.%Y"),
        expires_date=expires.astimezone(_DOCUMENT_TZ).strftime("%d.%m.%Y"),
        operator_name=str(operator.get("name") or ""),
        operator_status=str(operator.get("status") or ""),
        operator_inn=str(operator.get("inn") or ""),
        operator_details=str(operator.get("details") or ""),
        client_name=str(client.get("full_name") or ""),
        client_org=client.get("org"),
        client_details=_client_details_text(client) if client.get("details_complete") else "",
        scope=scope,
        schedule=schedule,
        price=payload.price_text.strip(),
        payment_terms=payment_terms,
        template_kind=parent.template_kind.value,
    )
    item = ServiceAgreement(
        agreement_number=number,
        lead_id=parent.lead_id,
        intake_id=parent.intake_id,
        parent_agreement_id=parent.id,
        revision=revision,
        supersedes_id=previous.id if previous else None,
        subject=f"Дополнительное соглашение № {supplement_no} к договору № {parent.agreement_number}",
        scope_text=scope,
        exclusions_text="",
        schedule_text=schedule,
        price_text=payload.price_text.strip(),
        amount_minor=payload.amount_minor,
        currency=parent.currency,
        payment_terms=payment_terms,
        created_by=identity.name,
        prepared_by_telegram_user_id=payload.prepared_by_telegram_user_id,
        operator_snapshot=operator,
        # Реквизиты клиента уже в подписанном договоре — второй раз их не
        # спрашиваем, поэтому бот и кабинет сразу открывают документ.
        client_snapshot={**client, "details_complete": True},
        template_kind=parent.template_kind,
        document_text=text,
        document_version=SUPPLEMENT_VERSION,
        document_hash=document_hash(text),
        expires_at=expires,
        client_telegram_user_id=parent.client_telegram_user_id,
    )
    db.add(item)
    db.flush()
    _audit(
        db,
        identity,
        item,
        "service_agreement.supplement",
        {
            "parent_id": str(parent.id),
            "parent_number": parent.agreement_number,
            "amount_from": parent.amount_minor,
            "amount_to": payload.amount_minor,
        },
    )
    body = _payload(item, include_text=True)
    if idempotency_key:
        store_response(db, idempotency_key, status.HTTP_201_CREATED, body, namespace=namespace)
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
            # Редакции договора по обращению; допсоглашения живут под своим договором.
            .where(ServiceAgreement.parent_agreement_id.is_(None))
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
        stmt = stmt.where(
            ServiceAgreement.status.not_in(
                {ServiceAgreementStatus.draft, ServiceAgreementStatus.superseded}
            )
        )
    rows = db.execute(stmt.order_by(ServiceAgreement.created_at.desc()).limit(20)).scalars().all()
    return [_payload(row) for row in rows]


@router.get("/{agreement_id}")
def get_agreement(
    agreement_id: uuid.UUID,
    telegram_user_id: int | None = Query(default=None),
    client_account_id: uuid.UUID | None = Query(default=None),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, agreement_id)
    if identity.scope == Scope.bot:
        if telegram_user_id is None and client_account_id is None:
            raise HTTPException(status_code=400, detail="telegram_user_id is required")
        _assert_client(db, item, telegram_user_id, client_account_id)
        if item.status == ServiceAgreementStatus.draft:
            raise HTTPException(status_code=404, detail="Agreement not found")
    return _payload(item, include_text=True)


def _certificate_rows(db: Session, item: ServiceAgreement) -> list[tuple[str, str]]:
    """Лист «Сведения о документе и подписании» — из того, что записала система."""
    from core_api.pdf_document import msk, text_hash

    operator = item.operator_snapshot or {}
    client = item.client_snapshot or {}
    customer = client.get("org") or client.get("full_name") or "—"
    rows: list[tuple[str, str]] = [
        ("Документ", f"{_document_title(item)} № {item.agreement_number}"),
    ]
    if _is_supplement(item):
        parent = db.get(ServiceAgreement, item.parent_agreement_id)
        rows.append(("К договору", f"№ {parent.agreement_number}" if parent else "—"))
    rows += [
        ("Редакция", str(item.revision)),
        ("Версия шаблона", item.document_version),
        ("Контрольная сумма SHA-256", item.document_hash),
        (
            "Текст совпадает с суммой",
            "да" if text_hash(item.document_text) == item.document_hash else "НЕТ — текст отличается",
        ),
        ("Исполнитель", ", ".join(x for x in (operator.get("name"), f"ИНН {operator['inn']}" if operator.get("inn") else "") if x) or "—"),
        ("Заказчик", str(customer)),
        ("Статус", STATUS_LABELS.get(item.status.value, item.status.value)),
        ("Сформирован", msk(item.created_at)),
        ("Отправлен клиенту", msk(item.sent_at)),
        ("Открыт клиентом", msk(item.viewed_at)),
    ]
    if item.signed_at:
        rows += [
            ("Подписан", msk(item.signed_at)),
            ("Подписант", item.signer_full_name or "—"),
            ("Telegram ID подписанта", str(item.signer_telegram_user_id or "—")),
        ]
        if item.signer_telegram_username:
            rows.append(("Аккаунт Telegram", f"@{item.signer_telegram_username}"))
        if item.signer_org:
            rows += [
                ("Организация", item.signer_org),
                ("Должность", item.signer_position or "—"),
                ("Основание полномочий", item.authority_basis or "—"),
            ]
    elif item.declined_at:
        rows.append(("Отклонён", msk(item.declined_at)))
    else:
        rows.append(("Подписан", "не подписан"))
    return rows


_CERTIFICATE_NOTE = (
    "Лист сформирован автоматически {now} из журнала системы AI Verdict и в текст документа не "
    "входит. Подписанием считается подтверждение Заказчиком в Telegram-боте или личном кабинете "
    "из своей учётной записи Telegram в порядке, установленном договором (раздел об электронном "
    "взаимодействии и подписи). Контрольная сумма SHA-256 вычисляется от точного текста документа "
    "в кодировке UTF-8: её совпадение подтверждает, что текст не менялся после формирования."
)


@router.get("/{agreement_id}/pdf", response_model=None)
def agreement_pdf(
    agreement_id: uuid.UUID,
    telegram_user_id: int | None = Query(default=None),
    client_account_id: uuid.UUID | None = Query(default=None),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> Response:
    """Точный текст договора или допсоглашения в PDF и лист сведений о подписании.

    Доступ — как у просмотра документа: клиенту только свой и не черновик.
    """
    from core_api.pdf_document import FontMissing, render

    item = _get(db, agreement_id)
    if identity.scope == Scope.bot:
        if telegram_user_id is None and client_account_id is None:
            raise HTTPException(status_code=400, detail="telegram_user_id is required")
        _assert_client(db, item, telegram_user_id, client_account_id)
        if item.status == ServiceAgreementStatus.draft:
            raise HTTPException(status_code=404, detail="Agreement not found")
    title = _document_title(item)
    try:
        content = render(
            text=item.document_text,
            footer_label=f"{title} № {item.agreement_number}",
            certificate_title="Сведения о документе и его подписании",
            certificate_rows=_certificate_rows(db, item),
            certificate_note=_CERTIFICATE_NOTE.format(now=datetime.now(_DOCUMENT_TZ).strftime("%d.%m.%Y %H:%M МСК")),
        )
    except FontMissing as exc:
        raise HTTPException(status_code=503, detail="PDF is unavailable") from exc
    prefix = "dopsoglashenie" if _is_supplement(item) else "dogovor"
    filename = f"{prefix}-{item.agreement_number}.pdf".replace("/", "-")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    # Допсоглашение уходит по делу, которое уже в работе: откатывать его к
    # «условия отправлены» было бы неправдой.
    if not _is_supplement(item):
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
    _assert_client(db, item, payload.telegram_user_id, payload.client_account_id)
    if item.status not in {ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed}:
        raise HTTPException(status_code=409, detail="Agreement is not available for viewing")
    if not (item.client_snapshot or {}).get("details_complete"):
        raise HTTPException(status_code=409, detail="Client details must be completed first")
    if payload.document_hash.lower() != item.document_hash:
        raise HTTPException(status_code=409, detail="Document hash mismatch")
    item.status = ServiceAgreementStatus.viewed
    item.viewed_at = item.viewed_at or _now()
    item.viewed_message_id = payload.message_id or item.viewed_message_id
    item.viewed_callback_id = payload.callback_id
    _audit(db, identity, item, "service_agreement.viewed")
    db.commit()
    return _payload(item)


@router.post("/{agreement_id}/client-details", status_code=status.HTTP_201_CREATED)
def complete_client_details(
    agreement_id: uuid.UUID,
    payload: AgreementClientDetails,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """Creates the signable revision from details entered by the client."""
    namespace = "service_agreements.client_details"
    if idempotency_key and (cached := cached_response(db, idempotency_key, namespace=namespace)):
        code, body = cached
        return JSONResponse(status_code=code, content=body)

    item = _get(db, agreement_id, lock=True)
    _assert_client(db, item, payload.telegram_user_id, payload.client_account_id)
    if item.status != ServiceAgreementStatus.sent:
        raise HTTPException(status_code=409, detail="Agreement draft is not awaiting details")
    if (item.client_snapshot or {}).get("details_complete"):
        raise HTTPException(status_code=409, detail="Client details are already completed")

    latest_id = db.execute(
        select(ServiceAgreement.id)
        .where(ServiceAgreement.intake_id == item.intake_id)
        .where(ServiceAgreement.parent_agreement_id.is_(None))
        .order_by(ServiceAgreement.revision.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest_id != item.id:
        raise HTTPException(status_code=409, detail="A newer agreement revision already exists")

    previous_client = item.client_snapshot or {}
    client = {
        "client_type": payload.client_type,
        "full_name": payload.full_name,
        "contact": payload.contact,
        "address": payload.address,
        "identity_document": payload.identity_document,
        "org": payload.org_name if payload.client_type == "organization" else None,
        "inn": payload.inn,
        "ogrn": payload.ogrn,
        "position": payload.position,
        "authority_basis": payload.authority_basis,
        "details_complete": True,
        "nda_id": previous_client.get("nda_id"),
        "nda_version": previous_client.get("nda_version"),
    }
    created = _now()
    expires = item.expires_at or (created + timedelta(days=7))
    revision = item.revision + 1
    number = item.agreement_number.split("-R", 1)[0]
    display_number = f"{number}-R{revision}"
    operator = item.operator_snapshot or {}
    text = render_agreement_text(
        number=display_number,
        revision=revision,
        created_date=created.strftime("%d.%m.%Y"),
        expires_date=expires.strftime("%d.%m.%Y"),
        operator_name=str(operator.get("name") or ""),
        operator_status=str(operator.get("status") or ""),
        operator_inn=str(operator.get("inn") or ""),
        operator_details=str(operator.get("details") or ""),
        client_name=client["full_name"],
        client_org=client["org"],
        client_details=_client_details_text(client),
        subject=item.subject,
        scope=item.scope_text,
        exclusions=item.exclusions_text,
        schedule=item.schedule_text,
        price=item.price_text,
        payment_terms=item.payment_terms,
        template_kind=item.template_kind.value,
    )
    item.status = ServiceAgreementStatus.superseded
    revised = ServiceAgreement(
        agreement_number=display_number,
        lead_id=item.lead_id,
        intake_id=item.intake_id,
        revision=revision,
        supersedes_id=item.id,
        subject=item.subject,
        scope_text=item.scope_text,
        exclusions_text=item.exclusions_text,
        schedule_text=item.schedule_text,
        price_text=item.price_text,
        amount_minor=item.amount_minor,
        currency=item.currency,
        payment_terms=item.payment_terms,
        created_by=item.created_by,
        prepared_by_telegram_user_id=item.prepared_by_telegram_user_id,
        operator_snapshot=operator,
        client_snapshot=client,
        template_kind=item.template_kind,
        document_text=text,
        document_version=agreement_version(item.template_kind.value),
        document_hash=document_hash(text),
        expires_at=expires,
        sent_at=created,
        client_telegram_user_id=item.client_telegram_user_id,
        sent_chat_id=item.sent_chat_id,
        sent_message_id=item.sent_message_id,
        sent_by_telegram_user_id=item.sent_by_telegram_user_id,
        sent_callback_id=item.sent_callback_id,
        status=ServiceAgreementStatus.sent,
    )
    db.add(revised)
    db.flush()
    messages = db.execute(
        select(ServiceAgreementMessage).where(ServiceAgreementMessage.agreement_id == item.id)
    ).scalars()
    for message in messages:
        message.agreement_id = revised.id
    _audit(
        db,
        identity,
        revised,
        "service_agreement.client_details",
        {"client_type": payload.client_type, "supersedes_id": str(item.id)},
    )
    body = _payload(revised, include_text=True)
    if idempotency_key:
        store_response(
            db,
            idempotency_key,
            status.HTTP_201_CREATED,
            body,
            namespace=namespace,
        )
    else:
        db.commit()
    return body


@router.post("/{agreement_id}/sign", status_code=status.HTTP_201_CREATED)
def sign_agreement(
    agreement_id: uuid.UUID,
    payload: AgreementSign,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, agreement_id, lock=True)
    principal = _assert_client(db, item, payload.telegram_user_id, payload.client_account_id)
    if item.status == ServiceAgreementStatus.signed:
        return {**_payload(item), "already_signed": True}
    # Подпись определена в NDA (п.6) как нажатие кнопки в Telegram. Для входа
    # через Яндекс ID нужна новая редакция этого пункта — до неё подписывать
    # можно только из Telegram.
    if principal.via_email:
        raise HTTPException(status_code=409, detail="Signing without Telegram is not available yet")
    if item.status != ServiceAgreementStatus.viewed:
        raise HTTPException(status_code=409, detail="Agreement must be viewed before signing")
    if payload.document_hash.lower() != item.document_hash:
        raise HTTPException(status_code=409, detail="Document hash mismatch")

    client = item.client_snapshot or {}
    if not client.get("details_complete"):
        raise HTTPException(status_code=409, detail="Client details must be completed first")
    signer_position = client.get("position") or payload.signer_position
    authority_basis = client.get("authority_basis") or payload.authority_basis
    if client.get("org") and (not signer_position or not authority_basis):
        raise HTTPException(status_code=422, detail="Position and authority basis are required")

    item.status = ServiceAgreementStatus.signed
    item.signed_at = _now()
    item.signer_telegram_user_id = principal.telegram_user_id
    item.signer_telegram_username = payload.telegram_username
    item.signer_full_name = client.get("full_name")
    item.signer_contact = client.get("contact")
    item.signer_org = client.get("org")
    item.signer_position = signer_position
    item.authority_basis = authority_basis
    item.signed_callback_id = payload.callback_id
    if _is_supplement(item):
        _apply_supplement(db, identity, item)
    else:
        if item.intake_id and (intake := db.get(LegalIntake, item.intake_id)):
            intake.status = LegalIntakeStatus.accepted
        if item.lead_id and (lead := db.get(Lead, item.lead_id)):
            lead.status = LeadStatus.won
    _audit(db, identity, item, "service_agreement.sign", {"version": item.document_version})
    if payload.channel == "miniapp":
        what = "допсоглашение" if _is_supplement(item) else "договор"
        queue_notice(
            db,
            f"agreement:{item.id}:signed",
            f"Клиент подписал {what} № {item.agreement_number} в кабинете.",
        )
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
    _assert_client(db, item, payload.telegram_user_id, payload.client_account_id)
    if item.status not in {ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed}:
        raise HTTPException(status_code=409, detail="Agreement cannot be declined")
    item.status = ServiceAgreementStatus.declined
    item.declined_at = _now()
    item.decline_reason = payload.reason
    item.declined_callback_id = payload.callback_id
    # Отказ от допсоглашения не отменяет подписанный договор: дело остаётся в работе.
    if not _is_supplement(item) and item.intake_id and (intake := db.get(LegalIntake, item.intake_id)):
        intake.status = LegalIntakeStatus.scope_preparation
    _audit(db, identity, item, "service_agreement.decline")
    if payload.channel == "miniapp":
        what = "допсоглашение" if _is_supplement(item) else "договор"
        queue_notice(
            db,
            f"agreement:{item.id}:declined",
            f"Клиент отклонил {what} № {item.agreement_number}."
            + (f" Причина: {item.decline_reason}" if item.decline_reason else ""),
        )
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
    if payload.telegram_user_id is None and payload.client_account_id is None:
        raise HTTPException(status_code=422, detail="telegram_user_id is required")
    principal = _assert_client(db, item, payload.telegram_user_id, payload.client_account_id)
    if item.status not in {ServiceAgreementStatus.sent, ServiceAgreementStatus.viewed}:
        raise HTTPException(status_code=409, detail="Agreement is not open for questions")
    msg = ServiceAgreementMessage(
        agreement_id=item.id,
        role=ServiceAgreementMessageRole.client,
        telegram_user_id=principal.telegram_user_id,
        text=payload.text.strip(),
    )
    db.add(msg)
    db.flush()
    _audit(db, identity, item, "service_agreement.question")
    if payload.channel == "miniapp":
        queue_notice(
            db,
            f"agreement:{item.id}:question:{msg.id}",
            f"Новый вопрос клиента по {'допсоглашению' if _is_supplement(item) else 'договору'}"
            f" № {item.agreement_number}:\n{msg.text}",
        )
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


def _client_bot_token() -> str:
    settings = get_settings()
    return (
        getattr(settings, "lead_bot_token", None)
        or getattr(settings, "lead_notify_bot_token", None)
        or ""
    )


@router.post("/{agreement_id}/deliver")
def deliver_agreement(
    agreement_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Отправляет клиенту подготовленный договор и отмечает отправку.

    Единственное место доставки: и кнопка в боте, и рабочее место юриста
    вызывают её. Пока текст и кнопки собирались в боте, отправка из другого
    места означала бы вторую копию, а разошедшиеся копии на этой неделе уже
    дважды приводили к тихим сбоям.

    Отметка ставится только после успешной отправки. Обратный порядок оставил
    бы договор «отправленным» при неудаче, и юрист ждал бы ответа, которого
    клиент не получал.
    """
    item = _get(db, agreement_id, lock=True)
    if item.status != ServiceAgreementStatus.draft:
        raise HTTPException(status_code=409, detail="Agreement is not a draft")
    if not item.client_telegram_user_id:
        raise HTTPException(status_code=409, detail="Client has no Telegram")

    token = _client_bot_token()
    if not token:
        raise HTTPException(status_code=500, detail="Bot token is not configured")

    payload = _payload(item)
    try:
        telegram_delivery.send(
            kind="agreement",
            token=token,
            chat_id=item.client_telegram_user_id,
            text=build_proposal_text(payload),
            reply_markup=build_proposal_markup(str(item.id), supplement=_is_supplement(item)),
            lead_id=item.lead_id,
            agreement_id=item.id,
            transport=_post_telegram_message,
        )
    except Exception as exc:  # noqa: BLE001 — причина уходит юристу, а не в трейс
        raise HTTPException(
            status_code=502, detail=f"Telegram delivery failed: {type(exc).__name__}"
        ) from exc

    item.status = ServiceAgreementStatus.sent
    item.sent_at = datetime.now(timezone.utc)
    db.add(item)
    _audit(db, identity, item, "service_agreement.deliver")
    db.commit()
    db.refresh(item)
    return _payload(item)


@router.post("/{agreement_id}/replies/deliver", status_code=status.HTTP_201_CREATED)
def reply_and_deliver(
    agreement_id: uuid.UUID,
    payload: AgreementMessageIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Записывает ответ юриста и сразу отправляет его клиенту.

    Отдельно от /replies: тот только записывает, и его вызывает бот, который
    отправляет сам. Здесь оба шага вместе — для рабочего места, у которого
    своего канала в Telegram нет.
    """
    item = _get(db, agreement_id)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    if not item.client_telegram_user_id:
        raise HTTPException(status_code=409, detail="Client has no Telegram")

    token = _client_bot_token()
    if not token:
        raise HTTPException(status_code=500, detail="Bot token is not configured")

    try:
        telegram_delivery.send(
            kind="agreement_reply",
            token=token,
            chat_id=item.client_telegram_user_id,
            text=build_reply_text(_payload(item), text),
            lead_id=item.lead_id,
            agreement_id=item.id,
            transport=_post_telegram_message,
        )
    except Exception as exc:  # noqa: BLE001
        # Не записываем ответ, который не дошёл: иначе в переписке он будет
        # выглядеть отправленным, и юрист решит, что клиент его проигнорировал.
        raise HTTPException(
            status_code=502, detail=f"Telegram delivery failed: {type(exc).__name__}"
        ) from exc

    msg = ServiceAgreementMessage(
        agreement_id=item.id,
        role=ServiceAgreementMessageRole.lawyer,
        telegram_user_id=payload.telegram_user_id,
        text=text,
    )
    db.add(msg)
    db.flush()
    _audit(db, identity, item, "service_agreement.reply")
    db.commit()
    return {"id": str(msg.id), "delivered": True}
