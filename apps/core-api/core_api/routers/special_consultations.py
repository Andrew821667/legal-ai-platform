from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.idempotency import cached_response, store_response
from core_api.models import (
    ActorType,
    Event,
    Lead,
    LeadSource,
    LeadStatus,
    PaymentTransactionStatus,
    Scope,
    SpecialConsultationOrder,
    SpecialConsultationOrderSource,
    SpecialConsultationOrderStatus,
    SpecialConsultationPayment,
    SpecialConsultationProduct,
)
from core_api.schemas import (
    SpecialConsultationOrderCreate,
    SpecialConsultationOrderOut,
    SpecialConsultationOrderPatch,
    SpecialConsultationPaymentCreate,
    SpecialConsultationPaymentEvent,
    SpecialConsultationPaymentEventResult,
    SpecialConsultationPaymentOut,
    SpecialConsultationProductOut,
    SpecialConsultationProductUpsert,
)

router = APIRouter(prefix="/api/v1/special-consultations", tags=["special-consultations"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _order_allows_payment(order: SpecialConsultationOrder) -> bool:
    return order.status not in {
        SpecialConsultationOrderStatus.fulfilled,
        SpecialConsultationOrderStatus.refunded,
    }


def _has_customer_context(payload: SpecialConsultationOrderCreate) -> bool:
    return any(
        [
            payload.telegram_user_id is not None,
            payload.customer_contact,
            payload.customer_email,
            payload.customer_phone,
            payload.customer_name,
            payload.customer_company,
        ]
    )


def _derive_lead_source(payload: SpecialConsultationOrderCreate) -> LeadSource:
    if payload.lead_source is not None:
        return payload.lead_source
    if payload.source == SpecialConsultationOrderSource.lead_bot:
        return LeadSource.telegram_bot
    return LeadSource.website_form


def _find_existing_lead(db: Session, payload: SpecialConsultationOrderCreate) -> Lead | None:
    if payload.telegram_user_id is not None:
        lead = db.execute(
            select(Lead).where(Lead.telegram_user_id == payload.telegram_user_id).limit(1)
        ).scalar_one_or_none()
        if lead is not None:
            return lead
    for field_name, value in (
        ("contact", payload.customer_contact),
        ("email", payload.customer_email),
        ("phone", payload.customer_phone),
    ):
        if value:
            column = getattr(Lead, field_name)
            lead = db.execute(select(Lead).where(column == value).limit(1)).scalar_one_or_none()
            if lead is not None:
                return lead
    return None


def _resolve_or_create_lead(db: Session, payload: SpecialConsultationOrderCreate) -> Lead | None:
    now = _now()
    if payload.lead_id is not None:
        lead = db.get(Lead, payload.lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead

    lead = _find_existing_lead(db, payload)
    if lead is not None:
        if payload.customer_name:
            lead.name = payload.customer_name
        if payload.customer_contact:
            lead.contact = payload.customer_contact
        if payload.customer_email:
            lead.email = payload.customer_email
        if payload.customer_phone:
            lead.phone = payload.customer_phone
        if payload.customer_company:
            lead.company = payload.customer_company
        if payload.telegram_user_id is not None:
            lead.telegram_user_id = payload.telegram_user_id
        if lead.service_category is None:
            lead.service_category = "special_paid_consultation"
        lead.last_activity_at = now
        db.add(lead)
        return lead

    if not _has_customer_context(payload):
        return None

    lead = Lead(
        source=_derive_lead_source(payload),
        telegram_user_id=payload.telegram_user_id,
        name=payload.customer_name,
        contact=payload.customer_contact,
        company=payload.customer_company,
        email=payload.customer_email,
        phone=payload.customer_phone,
        status=LeadStatus.new,
        service_category="special_paid_consultation",
        specific_need=payload.request_note,
        conversation_stage="special_consultation",
        notes=f"special_consultation:{payload.product_code}",
        last_activity_at=now,
    )
    db.add(lead)
    db.flush()
    return lead


def _serialize_order(order: SpecialConsultationOrder) -> dict:
    return SpecialConsultationOrderOut.model_validate(order).model_dump(mode="json")


def _serialize_payment(payment: SpecialConsultationPayment) -> dict:
    return SpecialConsultationPaymentOut.model_validate(payment).model_dump(mode="json")


def _apply_order_status_from_payment(
    order: SpecialConsultationOrder,
    payment: SpecialConsultationPayment,
) -> None:
    now = _now()
    if payment.status == PaymentTransactionStatus.paid:
        order.status = SpecialConsultationOrderStatus.paid
        order.paid_at = payment.paid_at or now
        return
    if payment.status == PaymentTransactionStatus.refunded:
        order.status = SpecialConsultationOrderStatus.refunded
        return
    if payment.status == PaymentTransactionStatus.cancelled:
        order.status = SpecialConsultationOrderStatus.cancelled
        order.cancelled_at = order.cancelled_at or now
        return

    if order.amount_minor is None:
        order.status = SpecialConsultationOrderStatus.awaiting_quote
    else:
        order.status = SpecialConsultationOrderStatus.awaiting_payment


@router.get("/products", response_model=list[SpecialConsultationProductOut])
def list_products(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
    active_only: bool = True,
) -> list[SpecialConsultationProduct]:
    _ = identity
    query = select(SpecialConsultationProduct)
    if active_only:
        query = query.where(SpecialConsultationProduct.is_active.is_(True))
    query = query.order_by(SpecialConsultationProduct.sort_order.asc(), SpecialConsultationProduct.code.asc())
    return list(db.execute(query).scalars().all())


@router.put("/products/{product_code}", response_model=SpecialConsultationProductOut)
def upsert_product(
    product_code: str,
    payload: SpecialConsultationProductUpsert,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> SpecialConsultationProduct:
    product = db.get(SpecialConsultationProduct, product_code)
    created = product is None
    if product is None:
        product = SpecialConsultationProduct(code=product_code)
        db.add(product)

    for key, value in payload.model_dump().items():
        setattr(product, key, value)

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="special_consultation.product.upsert",
        target_type="special_consultation_product",
        target_id=None,
        details={"code": product_code, "created": created},
    )
    db.commit()
    db.refresh(product)
    return product


@router.post("/orders", response_model=SpecialConsultationOrderOut)
def create_order(
    payload: SpecialConsultationOrderCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> SpecialConsultationOrder | JSONResponse:
    if idempotency_key:
        cached = cached_response(db, idempotency_key, namespace="special_consultation.orders.create")
        if cached:
            cached_status, cached_body = cached
            return JSONResponse(status_code=cached_status, content=cached_body)

    product = db.get(SpecialConsultationProduct, payload.product_code)
    if product is None or not product.is_active:
        raise HTTPException(status_code=404, detail="Special consultation product not found")

    lead = _resolve_or_create_lead(db, payload)
    if lead is None and not _has_customer_context(payload):
        raise HTTPException(
            status_code=422,
            detail="lead_id or customer identity fields are required for a special consultation order",
        )

    amount_minor = payload.amount_minor if payload.amount_minor is not None else product.base_price_minor
    status_value = (
        SpecialConsultationOrderStatus.awaiting_payment
        if amount_minor is not None
        else SpecialConsultationOrderStatus.awaiting_quote
    )
    order = SpecialConsultationOrder(
        lead_id=lead.id if lead is not None else None,
        product_code=product.code,
        source=payload.source,
        status=status_value,
        telegram_user_id=payload.telegram_user_id,
        customer_name=payload.customer_name,
        customer_contact=payload.customer_contact,
        customer_email=payload.customer_email,
        customer_phone=payload.customer_phone,
        customer_company=payload.customer_company,
        request_note=payload.request_note,
        currency=payload.currency,
        amount_minor=amount_minor,
        payment_due_at=payload.payment_due_at,
        context=payload.context,
    )
    db.add(order)
    db.flush()
    db.add(
        Event(
            lead_id=lead.id if lead is not None else None,
            type="special_consultation.order_created",
            payload={
                "order_id": str(order.id),
                "product_code": product.code,
                "source": payload.source.value,
                "status": status_value.value,
            },
        )
    )
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="special_consultation.order.create",
        target_type="special_consultation_order",
        target_id=order.id,
        details={
            "product_code": product.code,
            "source": payload.source.value,
            "lead_id": str(lead.id) if lead is not None else None,
            "status": status_value.value,
        },
    )
    db.commit()
    db.refresh(order)

    if idempotency_key:
        store_response(
            db,
            idempotency_key,
            status.HTTP_200_OK,
            _serialize_order(order),
            namespace="special_consultation.orders.create",
        )

    return order


@router.get("/orders", response_model=list[SpecialConsultationOrderOut])
def list_orders(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
    status_filter: SpecialConsultationOrderStatus | None = None,
    source_filter: SpecialConsultationOrderSource | None = None,
    lead_id: uuid.UUID | None = None,
    telegram_user_id: int | None = None,
    limit: int = 100,
) -> list[SpecialConsultationOrder]:
    _ = identity
    capped_limit = max(1, min(limit, 500))
    query = select(SpecialConsultationOrder)
    if status_filter is not None:
        query = query.where(SpecialConsultationOrder.status == status_filter)
    if source_filter is not None:
        query = query.where(SpecialConsultationOrder.source == source_filter)
    if lead_id is not None:
        query = query.where(SpecialConsultationOrder.lead_id == lead_id)
    if telegram_user_id is not None:
        query = query.where(SpecialConsultationOrder.telegram_user_id == telegram_user_id)
    query = query.order_by(SpecialConsultationOrder.created_at.desc()).limit(capped_limit)
    return list(db.execute(query).scalars().all())


@router.get("/orders/{order_id}", response_model=SpecialConsultationOrderOut)
def get_order(
    order_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> SpecialConsultationOrder:
    _ = identity
    order = db.get(SpecialConsultationOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Special consultation order not found")
    return order


@router.patch("/orders/{order_id}", response_model=SpecialConsultationOrderOut)
def patch_order(
    order_id: uuid.UUID,
    payload: SpecialConsultationOrderPatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> SpecialConsultationOrder:
    order = db.get(SpecialConsultationOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Special consultation order not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(order, key, value)

    now = _now()
    if payload.status == SpecialConsultationOrderStatus.paid:
        order.paid_at = order.paid_at or now
    elif payload.status == SpecialConsultationOrderStatus.cancelled:
        order.cancelled_at = order.cancelled_at or now
    elif payload.status == SpecialConsultationOrderStatus.fulfilled:
        order.fulfilled_at = payload.fulfilled_at or order.fulfilled_at or now

    db.add(order)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="special_consultation.order.update",
        target_type="special_consultation_order",
        target_id=order.id,
        details=updates,
    )
    db.commit()
    db.refresh(order)
    return order


@router.post("/orders/{order_id}/payments", response_model=SpecialConsultationPaymentOut)
def create_payment(
    order_id: uuid.UUID,
    payload: SpecialConsultationPaymentCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> SpecialConsultationPayment:
    order = db.get(SpecialConsultationOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Special consultation order not found")
    if not _order_allows_payment(order):
        raise HTTPException(status_code=409, detail="Payments are not allowed for this order status")

    amount_minor = payload.amount_minor if payload.amount_minor is not None else order.amount_minor
    if amount_minor is None:
        raise HTTPException(status_code=422, detail="Order amount must be set before creating a payment")

    payment_status = (
        PaymentTransactionStatus.requires_action if payload.confirmation_url else PaymentTransactionStatus.pending
    )
    payment = SpecialConsultationPayment(
        order_id=order.id,
        provider=payload.provider,
        status=payment_status,
        amount_minor=amount_minor,
        currency=(payload.currency or order.currency),
        provider_payment_id=payload.provider_payment_id,
        external_reference=payload.external_reference,
        confirmation_url=payload.confirmation_url,
        last_event_at=_now(),
        raw_payload=payload.raw_payload,
    )
    order.amount_minor = amount_minor
    order.currency = payload.currency or order.currency
    order.status = SpecialConsultationOrderStatus.awaiting_payment

    db.add(payment)
    db.add(order)
    db.flush()
    db.add(
        Event(
            lead_id=order.lead_id,
            type="special_consultation.payment_created",
            payload={
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "provider": payload.provider.value,
                "status": payment.status.value,
                "amount_minor": amount_minor,
            },
        )
    )
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="special_consultation.payment.create",
        target_type="special_consultation_payment",
        target_id=payment.id,
        details={
            "order_id": str(order.id),
            "provider": payload.provider.value,
            "status": payment.status.value,
        },
    )
    db.commit()
    db.refresh(payment)
    return payment


@router.post("/payments/events", response_model=SpecialConsultationPaymentEventResult)
def reconcile_payment_event(
    payload: SpecialConsultationPaymentEvent,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> SpecialConsultationPaymentEventResult:
    payment = None
    if payload.provider_payment_id:
        payment = db.execute(
            select(SpecialConsultationPayment)
            .where(SpecialConsultationPayment.provider == payload.provider)
            .where(SpecialConsultationPayment.provider_payment_id == payload.provider_payment_id)
            .limit(1)
        ).scalar_one_or_none()
    if payment is None and payload.external_reference:
        payment = db.execute(
            select(SpecialConsultationPayment)
            .where(SpecialConsultationPayment.external_reference == payload.external_reference)
            .limit(1)
        ).scalar_one_or_none()
    if payment is None and payload.order_id is not None:
        payment = db.execute(
            select(SpecialConsultationPayment)
            .where(SpecialConsultationPayment.order_id == payload.order_id)
            .where(SpecialConsultationPayment.provider == payload.provider)
            .order_by(SpecialConsultationPayment.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Special consultation payment not found")

    order = db.get(SpecialConsultationOrder, payment.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Special consultation order not found")

    if payload.provider_payment_id:
        payment.provider_payment_id = payload.provider_payment_id
    if payload.external_reference:
        payment.external_reference = payload.external_reference
    if payload.confirmation_url:
        payment.confirmation_url = payload.confirmation_url
    if payload.amount_minor is not None:
        payment.amount_minor = payload.amount_minor
        order.amount_minor = payload.amount_minor
    if payload.currency is not None:
        payment.currency = payload.currency
        order.currency = payload.currency
    payment.status = payload.status
    payment.last_event_at = _now()
    payment.raw_payload = payload.raw_payload
    if payload.status == PaymentTransactionStatus.paid:
        payment.paid_at = payment.paid_at or payment.last_event_at

    _apply_order_status_from_payment(order, payment)
    db.add(payment)
    db.add(order)
    db.add(
        Event(
            lead_id=order.lead_id,
            type="special_consultation.payment_status_changed",
            payload={
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "provider": payload.provider.value,
                "status": payload.status.value,
            },
        )
    )
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="special_consultation.payment.reconcile",
        target_type="special_consultation_payment",
        target_id=payment.id,
        details={
            "order_id": str(order.id),
            "provider": payload.provider.value,
            "status": payload.status.value,
        },
    )
    db.commit()
    db.refresh(order)
    db.refresh(payment)
    return SpecialConsultationPaymentEventResult(
        order=SpecialConsultationOrderOut.model_validate(order),
        payment=SpecialConsultationPaymentOut.model_validate(payment),
    )
