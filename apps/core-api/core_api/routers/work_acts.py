"""Акт с отдельными подтверждениями приёмки и поступления оплаты."""

from __future__ import annotations

import hashlib
import html
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.client_notices import queue_notice
from core_api.config import get_settings
from core_api.db import get_db
from core_api import npd_limit, payment_qr, telegram_delivery
from core_api.lead_notifications import _post_telegram_message
from core_api.models import (
    ActorType,
    Scope,
    ServiceAgreement,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)

router = APIRouter(prefix="/api/v1/work-acts", tags=["work-acts"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _next_act_number() -> str:
    return f"AC-{_now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def _client_bot_token() -> str:
    settings = get_settings()
    return (
        getattr(settings, "lead_bot_token", None)
        or getattr(settings, "lead_notify_bot_token", None)
        or ""
    )


def _format_rub(amount_minor: int) -> str:
    rubles, kopecks = divmod(amount_minor, 100)
    whole = f"{rubles:,}".replace(",", " ")
    return f"{whole},{kopecks:02d} ₽" if kopecks else f"{whole} ₽"


def _get(db: Session, act_id: uuid.UUID, *, lock: bool = False) -> WorkAct:
    stmt = select(WorkAct).where(WorkAct.id == act_id)
    if lock:
        stmt = stmt.with_for_update()
    item = db.execute(stmt).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Act not found")
    return item


def _payload(item: WorkAct) -> dict:
    return {
        "id": str(item.id),
        "act_number": item.act_number,
        "agreement_id": str(item.agreement_id),
        "lead_id": str(item.lead_id) if item.lead_id else None,
        "status": item.status.value,
        "description_text": item.description_text,
        "amount_minor": item.amount_minor,
        "currency": item.currency,
        "created_at": _iso(item.created_at),
        "sent_at": _iso(item.sent_at),
        "claimed_paid_at": _iso(item.claimed_paid_at),
        "paid_at": _iso(item.paid_at),
        "last_reminded_at": _iso(item.last_reminded_at),
        "receipt_ref": item.receipt_ref,
        "receipt_at": _iso(item.receipt_at),
        "receipt_sent_at": _iso(item.receipt_sent_at),
        "paid_note": item.paid_note,
        "document_hash": item.document_hash,
        "document_version": item.document_version,
        "viewed_at": _iso(item.viewed_at),
        "accepted_at": _iso(item.accepted_at),
        "objected_at": _iso(item.objected_at),
        "objection_text": item.objection_text,
        "cancelled_at": _iso(item.cancelled_at),
        "cancel_reason": item.cancel_reason,
    }


def _audit(
    db: Session,
    identity: ApiKeyIdentity,
    item: WorkAct,
    action: str,
    details: dict | None = None,
) -> None:
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action=action,
        target_type="work_act",
        target_id=item.id,
        details=details or {},
    )


class ActCreate(BaseModel):
    agreement_id: uuid.UUID
    description_text: str = Field(min_length=2, max_length=4000)
    amount_minor: int = Field(ge=0, le=10**13)
    prepared_by_telegram_user_id: int | None = Field(default=None, gt=0)


@router.post("", status_code=201)
def create_act(
    payload: ActCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Исполнитель фиксирует результат по подписанному договору."""
    agreement = db.get(ServiceAgreement, payload.agreement_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if agreement.status != ServiceAgreementStatus.signed:
        raise HTTPException(status_code=409, detail="Act can only be issued for a signed agreement")
    # Работы по допсоглашению — это работы по договору: акт выставляется по
    # нему, иначе у одного дела оказалось бы два независимых счёта актов.
    if agreement.parent_agreement_id is not None:
        raise HTTPException(status_code=409, detail="Issue the act under the main agreement")

    item = WorkAct(
        act_number=_next_act_number(),
        agreement_id=agreement.id,
        lead_id=agreement.lead_id,
        description_text=payload.description_text.strip(),
        amount_minor=payload.amount_minor,
        currency=agreement.currency,
        prepared_by_telegram_user_id=payload.prepared_by_telegram_user_id,
    )
    if not item.description_text:
        raise HTTPException(status_code=422, detail="Describe completed work")
    _freeze_document(item, agreement)
    db.add(item)
    db.flush()
    _audit(db, identity, item, "work_act.create")
    db.commit()
    db.refresh(item)
    return _payload(item)


@router.get("/by-agreement/{agreement_id}")
def list_by_agreement(
    agreement_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = identity
    rows = (
        db.execute(
            select(WorkAct)
            .where(WorkAct.agreement_id == agreement_id)
            .order_by(WorkAct.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_payload(row) for row in rows]


def _freeze_document(item: WorkAct, agreement: ServiceAgreement) -> None:
    if item.document_hash:
        return
    item.document_version = "2026-09-13.1"
    item.document_text = "\n".join([
        f"АКТ ВЫПОЛНЕННЫХ РАБОТ № {item.act_number}",
        f"К договору № {agreement.agreement_number}",
        f"Исполнитель: {(agreement.operator_snapshot or {}).get('name') or 'Исполнитель по договору'}",
        f"Заказчик: {(agreement.client_snapshot or {}).get('full_name') or 'Заказчик по договору'}",
        "", item.description_text, "",
        f"Стоимость работ: {_format_rub(item.amount_minor)}",
        "Приёмка работы и подтверждение оплаты фиксируются отдельно.",
    ])
    item.document_hash = hashlib.sha256(item.document_text.encode("utf-8")).hexdigest()


def payment_details() -> dict:
    settings = get_settings()
    qr = payment_qr.requisites() is not None
    phone = settings.lawyer_payment_sbp_phone
    if not phone and not qr:
        return {}
    return {"phone": phone, "bank": settings.lawyer_payment_bank,
            "recipient": settings.lawyer_payment_recipient,
            # Есть реквизиты счёта — у акта есть платёжный QR.
            "qr": qr}


def _build_act_text(item: WorkAct, agreement: ServiceAgreement) -> str:
    lines = [
        f"Акт выполненных работ № {html.escape(item.act_number)}",
        f"К договору № {html.escape(agreement.agreement_number)}",
        "",
        html.escape(item.description_text[:700]) + ("…" if len(item.description_text) > 700 else ""),
        "",
        f"К оплате: {_format_rub(item.amount_minor)}",
    ]
    payment = payment_details()
    details = [f"Телефон для перевода: <code>{html.escape(payment['phone'])}</code>"] if payment else []
    for label, key in (("Банк", "bank"), ("Получатель", "recipient")):
        if payment.get(key):
            details.append(f"{label}: {html.escape(payment[key])}")
    if details:
        # Реквизиты в <code> — Telegram копирует такой текст по тапу, без
        # выделения вручную.
        lines += ["", "Оплата:"] + details
    return "\n".join(lines + ["", "Откройте полный акт, чтобы принять работу или оставить замечания."])


def _act_markup(act_id: str) -> str:
    rows = [[{"text": "Открыть акт", "callback_data": f"act_c:open:{act_id}"}]]
    # Реквизиты счёта заданы — QR, который банк заполнит сам, вместо ручного
    # набора суммы при переводе по телефону.
    if payment_qr.requisites() is not None:
        rows.append([{"text": "QR для оплаты", "callback_data": f"act_c:qr:{act_id}"}])
    rows.append([{"text": "Я оплатил(а)", "callback_data": f"act_c:claim:{act_id}"}])
    return json.dumps({"inline_keyboard": rows}, ensure_ascii=False)


@router.post("/{act_id}/send")
def send_act(
    act_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Отправляет акт клиенту и отмечает отправку.

    Единственное место доставки — тот же приём, что у deliver_agreement: и
    кнопка в боте, и рабочее место юриста вызывают эту, а не собирают текст
    каждый по-своему.
    """
    item = _get(db, act_id, lock=True)
    if item.status != WorkActStatus.draft or item.cancelled_at:
        raise HTTPException(status_code=409, detail="Act is not a draft")
    agreement = db.get(ServiceAgreement, item.agreement_id)
    if agreement is None or not agreement.client_telegram_user_id:
        raise HTTPException(status_code=409, detail="Client has no Telegram")
    _freeze_document(item, agreement)

    token = _client_bot_token()
    if not token:
        raise HTTPException(status_code=500, detail="Bot token is not configured")

    try:
        sent = telegram_delivery.send(
            kind="work_act",
            token=token,
            chat_id=agreement.client_telegram_user_id,
            text=_build_act_text(item, agreement),
            reply_markup=_act_markup(str(item.id)),
            parse_mode="HTML",
            lead_id=item.lead_id,
            agreement_id=agreement.id,
            act_id=item.id,
            transport=_post_telegram_message,
        )
    except Exception as exc:  # noqa: BLE001 — причина уходит юристу, а не в трейс
        raise HTTPException(
            status_code=502, detail=f"Telegram delivery failed: {type(exc).__name__}"
        ) from exc

    item.status = WorkActStatus.sent
    item.sent_at = _now()
    item.sent_chat_id = agreement.client_telegram_user_id
    item.sent_message_id = sent.get("message_id")
    db.add(item)
    _audit(db, identity, item, "work_act.send")
    db.commit()
    db.refresh(item)
    return _payload(item)


# Напоминать об оплате не чаще раза в сутки: чаще — уже давление.
_REMIND_EVERY_HOURS = 24


def _build_reminder_text(item: WorkAct, agreement: ServiceAgreement) -> str:
    lines = [
        f"Напоминаем об оплате по акту № {html.escape(item.act_number)}",
        f"к договору № {html.escape(agreement.agreement_number)}.",
        "",
        f"К оплате: {_format_rub(item.amount_minor)}",
    ]
    payment = payment_details()
    if payment:
        lines += ["", f"Телефон для перевода: <code>{html.escape(payment['phone'])}</code>"]
        for label, key in (("Банк", "bank"), ("Получатель", "recipient")):
            if payment.get(key):
                lines.append(f"{label}: {html.escape(payment[key])}")
    lines += ["", "Если уже оплатили — нажмите «Я оплатил(а)», и юрист сверит поступление."]
    return "\n".join(lines)


@router.post("/{act_id}/remind")
def remind_payment(
    act_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Юрист напоминает клиенту об оплате акта — тем же ботом, что прислал акт.

    Только для акта, который ждёт оплаты и о котором клиент ещё не сказал
    «я оплатил»: иначе напоминание придёт тому, кто уже заплатил.
    """
    item = db.get(WorkAct, act_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Act not found")
    if item.cancelled_at or item.status != WorkActStatus.sent:
        raise HTTPException(status_code=409, detail="Act is not awaiting payment")
    now = _now()
    if item.last_reminded_at and (now - item.last_reminded_at).total_seconds() < _REMIND_EVERY_HOURS * 3600:
        raise HTTPException(status_code=409, detail="Payment reminder was already sent today")
    agreement = db.get(ServiceAgreement, item.agreement_id)
    if agreement is None or not agreement.client_telegram_user_id:
        raise HTTPException(status_code=409, detail="Client has no Telegram")
    token = _client_bot_token()
    if not token:
        raise HTTPException(status_code=500, detail="Bot token is not configured")
    try:
        telegram_delivery.send(
            kind="act_reminder",
            token=token,
            chat_id=agreement.client_telegram_user_id,
            text=_build_reminder_text(item, agreement),
            reply_markup=_act_markup(str(item.id)),
            parse_mode="HTML",
            lead_id=item.lead_id,
            agreement_id=agreement.id,
            act_id=item.id,
            transport=_post_telegram_message,
        )
    except Exception as exc:  # noqa: BLE001 — причина уходит юристу, а не в трейс
        raise HTTPException(
            status_code=502, detail=f"Telegram delivery failed: {type(exc).__name__}"
        ) from exc
    item.last_reminded_at = now
    _audit(db, identity, item, "work_act.remind")
    db.commit()
    return {"act_id": str(item.id), "last_reminded_at": now.isoformat()}


class ClaimPaid(BaseModel):
    telegram_user_id: int = Field(gt=0)
    channel: str = Field(default="telegram_bot", pattern=r"^(telegram_bot|miniapp)$")


@router.post("/{act_id}/claim-paid")
def claim_paid(
    act_id: uuid.UUID,
    payload: ClaimPaid,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    """Клиент нажал «Я оплатил(а)» — заявление, не подтверждение: реальную
    оплату видит только юрист, он и переводит статус в paid отдельно."""
    item = _get(db, act_id, lock=True)
    agreement = db.get(ServiceAgreement, item.agreement_id)
    if agreement is None or agreement.client_telegram_user_id != payload.telegram_user_id:
        # Тот же id акта не должен уходить в paid по чужому клику — даже
        # заявление о нём принимаем только от адресата.
        raise HTTPException(status_code=403, detail="Not the client of this act")
    if item.cancelled_at or item.status not in (WorkActStatus.sent, WorkActStatus.claimed_paid, WorkActStatus.paid):
        raise HTTPException(status_code=409, detail="Act is not awaiting payment")
    if item.status == WorkActStatus.sent:
        item.status = WorkActStatus.claimed_paid
        item.claimed_paid_at = _now()
        db.add(item)
        _audit(db, identity, item, "work_act.claim_paid")
        if payload.channel == "miniapp":
            queue_notice(
                db,
                f"work-act:{item.id}:claimed-paid",
                f"Клиент сообщил об оплате акта № {item.act_number}. Проверьте поступление.",
            )
        db.commit()
        db.refresh(item)
    return _payload(item)


class MarkPaid(BaseModel):
    paid_by_telegram_user_id: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)


@router.patch("/{act_id}/paid")
def mark_paid(
    act_id: uuid.UUID,
    payload: MarkPaid,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Юрист подтверждает получение денег — из sent (сразу, без клика
    клиента) или из claimed_paid (клиент уже заявил)."""
    item = _get(db, act_id, lock=True)
    if item.cancelled_at or item.status not in (WorkActStatus.sent, WorkActStatus.claimed_paid):
        raise HTTPException(status_code=409, detail="Act is not awaiting payment")
    item.status = WorkActStatus.paid
    item.paid_at = _now()
    item.paid_by_telegram_user_id = payload.paid_by_telegram_user_id
    item.paid_note = payload.note.strip() if payload.note else None
    db.add(item)
    _audit(db, identity, item, "work_act.paid", {"note": item.paid_note} if item.paid_note else None)
    db.flush()
    # Оплата двигает годовой доход к лимиту самозанятого — пройден порог,
    # владелец узнает сразу, а не в конце года.
    npd_limit.notify_if_crossed(db, item.paid_at)
    db.commit()
    db.refresh(item)
    return _payload(item)


class ReceiptIn(BaseModel):
    # Ссылка на чек из «Мой налог» или его номер. Пусто — «чек выдан»,
    # когда номер под рукой не сохранили.
    ref: str | None = Field(default=None, max_length=500)
    send_to_client: bool = False


@router.post("/{act_id}/receipt")
def record_receipt(
    act_id: uuid.UUID,
    payload: ReceiptIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Чек самозанятого по оплаченному акту: записать и, если надо, отправить.

    Самозанятый обязан передать покупателю чек при расчёте — в том числе
    ссылкой. Система знала об оплате, но не о чеке, и держалось всё на памяти.
    Отправка — тем же ботом, что прислал клиенту акт.
    """
    item = _get(db, act_id, lock=True)
    if item.cancelled_at or item.status != WorkActStatus.paid:
        raise HTTPException(status_code=409, detail="Receipt is recorded for a paid act")
    ref = (payload.ref or "").strip() or None
    now = _now()
    if payload.send_to_client:
        if not ref or not ref.lower().startswith("https://"):
            raise HTTPException(status_code=422, detail="Receipt link is required to send it")
        agreement = db.get(ServiceAgreement, item.agreement_id)
        if agreement is None or not agreement.client_telegram_user_id:
            raise HTTPException(status_code=409, detail="Client has no Telegram")
        token = _client_bot_token()
        if not token:
            raise HTTPException(status_code=500, detail="Bot token is not configured")
        try:
            telegram_delivery.send(
                kind="receipt",
                token=token,
                chat_id=agreement.client_telegram_user_id,
                text=(
                    f"Чек по акту № {item.act_number} на {_format_rub(item.amount_minor)}:\n{ref}\n\n"
                    "Спасибо за оплату."
                ),
                lead_id=item.lead_id,
                agreement_id=agreement.id,
                act_id=item.id,
                transport=_post_telegram_message,
            )
        except Exception as exc:  # noqa: BLE001 — причина уходит юристу, а не в трейс
            raise HTTPException(
                status_code=502, detail=f"Telegram delivery failed: {type(exc).__name__}"
            ) from exc
        item.receipt_sent_at = now
    item.receipt_ref = ref or item.receipt_ref
    item.receipt_at = item.receipt_at or now
    _audit(db, identity, item, "work_act.receipt", {"sent": bool(payload.send_to_client)})
    db.commit()
    db.refresh(item)
    return _payload(item)


def _assert_client(db: Session, item: WorkAct, telegram_user_id: int) -> None:
    agreement = db.get(ServiceAgreement, item.agreement_id)
    if agreement is None or agreement.client_telegram_user_id != telegram_user_id:
        raise HTTPException(status_code=404, detail="Act not found")
    if item.status == WorkActStatus.draft:
        raise HTTPException(status_code=404, detail="Act not found")


class ActClientAction(BaseModel):
    telegram_user_id: int = Field(gt=0)
    document_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    callback_id: str = Field(min_length=1, max_length=255)
    text: str | None = Field(default=None, max_length=4000)
    channel: str = Field(default="telegram_bot", pattern=r"^(telegram_bot|miniapp)$")


@router.get("/{act_id}/document")
def act_document(
    act_id: uuid.UUID,
    telegram_user_id: int = Query(gt=0),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, act_id)
    _assert_client(db, item, telegram_user_id)
    return {**_payload(item), "text": item.document_text, "payment": payment_details()}


@router.get("/{act_id}/payment-qr", response_model=None)
def act_payment_qr(
    act_id: uuid.UUID,
    telegram_user_id: int | None = Query(default=None, gt=0),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> Response:
    """Платёжный QR акта (ГОСТ Р 56042): реквизиты, сумма и назначение для банка.

    Клиенту — только свой акт и только пока он ждёт оплаты: QR на оплаченный
    или отозванный акт привёл бы к лишнему переводу.
    """
    item = _get(db, act_id)
    if identity.scope == Scope.bot:
        if telegram_user_id is None:
            raise HTTPException(status_code=400, detail="telegram_user_id is required")
        _assert_client(db, item, telegram_user_id)
    if item.cancelled_at or item.status not in (WorkActStatus.sent, WorkActStatus.claimed_paid):
        raise HTTPException(status_code=409, detail="Act is not awaiting payment")
    agreement = db.get(ServiceAgreement, item.agreement_id)
    purpose = f"Оплата по акту № {item.act_number}"
    if agreement is not None:
        purpose += f" к договору № {agreement.agreement_number}"
    data = payment_qr.payload(item.amount_minor, purpose + ". НДС не облагается")
    if data is None:
        raise HTTPException(status_code=404, detail="Payment QR is not configured")
    return Response(
        content=payment_qr.png(data),
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="qr-{item.act_number}.png"', "Cache-Control": "no-store"},
    )


@router.post("/{act_id}/client/{action}")
def client_action(
    act_id: uuid.UUID,
    action: str,
    payload: ActClientAction,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin, Scope.bot)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, act_id, lock=True)
    _assert_client(db, item, payload.telegram_user_id)
    if item.cancelled_at or not item.document_hash or item.document_hash != payload.document_hash:
        raise HTTPException(status_code=409, detail="Act is unavailable or document changed")
    if action == "viewed":
        if item.viewed_at:
            return _payload(item)
        item.viewed_at = _now()
    elif action in ("accept", "object"):
        if not item.viewed_at:
            raise HTTPException(status_code=409, detail="Read the act first")
        if item.accepted_at:
            if action == "accept":
                return _payload(item)
            raise HTTPException(status_code=409, detail="Act already accepted; contact the operator")
        if action == "accept":
            if item.objected_at:
                raise HTTPException(status_code=409, detail="Resolve objections and issue a new act first")
            item.accepted_at = _now()
            item.accepted_by_telegram_user_id = payload.telegram_user_id
            item.acceptance_callback_id = payload.callback_id
            if payload.channel == "miniapp":
                queue_notice(
                    db,
                    f"work-act:{item.id}:accepted",
                    f"Клиент принял работу по акту № {item.act_number}.",
                )
        else:
            text = (payload.text or "").strip()
            if not text:
                raise HTTPException(status_code=422, detail="Describe objections")
            if item.objected_at:
                if text == item.objection_text:
                    return _payload(item)
                raise HTTPException(status_code=409, detail="Objections already recorded; contact the operator")
            item.objection_text = text
            item.objected_at = _now()
            if payload.channel == "miniapp":
                queue_notice(
                    db,
                    f"work-act:{item.id}:objected",
                    f"Клиент оставил замечания к акту № {item.act_number}:\n{text}",
                    f"act_a:cancel:{item.id}",
                )
    else:
        raise HTTPException(status_code=404, detail="Unknown act action")
    _audit(db, identity, item, f"work_act.{action}", {
        "telegram_user_id": payload.telegram_user_id, "document_hash": item.document_hash,
        "callback_id": payload.callback_id,
    })
    db.commit()
    db.refresh(item)
    return _payload(item)


class ActCancel(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/{act_id}/cancel")
def cancel_act(
    act_id: uuid.UUID,
    payload: ActCancel,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    item = _get(db, act_id, lock=True)
    if item.accepted_at or item.status in (WorkActStatus.claimed_paid, WorkActStatus.paid):
        raise HTTPException(status_code=409, detail="Accepted or paid act cannot be cancelled")
    if not item.cancelled_at:
        item.cancelled_at = _now()
        item.cancel_reason = payload.reason.strip()
        _audit(db, identity, item, "work_act.cancel")
        db.commit()
        db.refresh(item)
    return _payload(item)
