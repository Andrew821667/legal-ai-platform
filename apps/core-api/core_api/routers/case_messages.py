"""Переписка по делу: клиент пишет из кабинета или бота, юрист отвечает из рабочего места.

Клиент без Telegram раньше не мог ни написать по делу (кнопка вела в бота,
который без VPN не открывается), ни получить ответ. Теперь тред хранится в
ядре и виден в кабинете при любом способе входа; клиенту с Telegram ответ
юриста приходит ещё и туда.

Уведомления юристу о новых сообщениях — без имени и текста клиента: они идут
через Telegram, серверы которого за рубежом (см. lead_notifications.telegram_safe).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from core_api import telegram_delivery
from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.client_notices import queue_notice
from core_api.client_principal import ClientRef, resolve, resolve_ref
from core_api.db import get_db
from core_api.models import ActorType, CaseMessage, Lead, LegalIntake, Scope

logger = logging.getLogger(__name__)

client = APIRouter(prefix="/api/v1/client-portal/cases", tags=["client-portal"])
lawyer = APIRouter(prefix="/api/v1/lawyer/clients", tags=["lawyer-workspace"])

MAX_TEXT = 4000


class ClientMessageIn(ClientRef):
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    channel: str = Field(default="cabinet", pattern=r"^(cabinet|telegram)$")


class LawyerMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    intake_id: uuid.UUID | None = None


def _row(message: CaseMessage) -> dict:
    return {
        "id": str(message.id),
        "intake_id": str(message.intake_id) if message.intake_id else None,
        "author": message.author,
        "channel": message.channel,
        "text": message.text,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "read_at": message.read_at.isoformat() if message.read_at else None,
    }


def _client_intake(db: Session, intake_id: uuid.UUID, lead_ids: frozenset[uuid.UUID]) -> LegalIntake:
    """Дело — только среди обращений самого клиента: идентификатор приходит из ссылки."""
    intake = db.get(LegalIntake, intake_id)
    if intake is None or intake.lead_id not in lead_ids:
        raise HTTPException(status_code=404, detail="Case not found")
    return intake


def unread_for_client(db: Session, intake_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Ответы юриста, которые клиент ещё не открыл, — по делам."""
    if not intake_ids:
        return {}
    rows = db.execute(
        select(CaseMessage.intake_id, func.count())
        .where(CaseMessage.intake_id.in_(intake_ids), CaseMessage.author == "lawyer", CaseMessage.read_at.is_(None))
        .group_by(CaseMessage.intake_id)
    ).all()
    return {intake_id: count for intake_id, count in rows}


# ---- Клиент ---------------------------------------------------------------


@client.get("/{intake_id}/messages")
def client_thread(
    intake_id: uuid.UUID,
    telegram_user_id: int | None = Query(default=None, gt=0),
    client_account_id: uuid.UUID | None = Query(default=None),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Переписка по делу; открыта клиентом — ответы юриста считаются прочитанными."""
    _ = identity
    if telegram_user_id is None and client_account_id is None:
        raise HTTPException(status_code=400, detail="telegram_user_id or client_account_id is required")
    principal = resolve(db, telegram_user_id=telegram_user_id, client_account_id=client_account_id)
    intake = _client_intake(db, intake_id, principal.lead_ids)
    messages = list(db.scalars(
        select(CaseMessage).where(CaseMessage.intake_id == intake.id).order_by(CaseMessage.created_at)
    ))
    db.execute(
        update(CaseMessage)
        .where(CaseMessage.intake_id == intake.id, CaseMessage.author == "lawyer", CaseMessage.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return {"intake_id": str(intake.id), "messages": [_row(message) for message in messages]}


@client.post("/{intake_id}/messages", status_code=status.HTTP_201_CREATED)
def client_write(
    intake_id: uuid.UUID,
    payload: ClientMessageIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    principal = resolve_ref(db, payload)
    intake = _client_intake(db, intake_id, principal.lead_ids)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    message = CaseMessage(lead_id=intake.lead_id, intake_id=intake.id, author="client",
                          channel=payload.channel, text=text)
    db.add(message)
    db.flush()
    # Без имени и текста: уведомление идёт юристу через Telegram.
    queue_notice(
        db,
        f"case-message:{message.id}",
        "💬 Клиент написал по своему обращению. Сообщение — в рабочем месте, в карточке клиента «Переписка».",
    )
    write_audit(db, actor_type=ActorType.api_key, actor_id=identity.name, action="case_message.client",
                target_type="legal_intake", target_id=intake.id, details={"channel": payload.channel})
    db.commit()
    db.refresh(message)
    return _row(message)


# ---- Юрист ----------------------------------------------------------------


def _lead(db: Session, lead_id: uuid.UUID) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@lawyer.get("/{lead_id}/messages")
def lawyer_thread(
    lead_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Вся переписка с клиентом; открыта юристом — сообщения клиента прочитаны."""
    _ = identity
    lead = _lead(db, lead_id)
    messages = list(db.scalars(
        select(CaseMessage).where(CaseMessage.lead_id == lead.id).order_by(CaseMessage.created_at)
    ))
    db.execute(
        update(CaseMessage)
        .where(CaseMessage.lead_id == lead.id, CaseMessage.author == "client", CaseMessage.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return {
        "lead_id": str(lead.id),
        # Куда дойдёт ответ: с Telegram — туда и в кабинет, без него — только в кабинет.
        "client_has_telegram": lead.telegram_user_id is not None,
        "messages": [_row(message) for message in messages],
    }


@lawyer.post("/{lead_id}/messages", status_code=status.HTTP_201_CREATED)
def lawyer_reply(
    lead_id: uuid.UUID,
    payload: LawyerMessageIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Ответ юриста. Сохраняется всегда — клиент увидит его в кабинете; клиенту
    с Telegram он приходит ещё и туда с кнопкой «Ответить по делу»."""
    lead = _lead(db, lead_id)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    intake_id = payload.intake_id
    if intake_id is not None:
        intake = db.get(LegalIntake, intake_id)
        if intake is None or intake.lead_id != lead.id:
            raise HTTPException(status_code=404, detail="Case not found")
    else:
        # Без явного дела — последнее обращение клиента: в кабинете тред живёт в карточке дела.
        intake_id = db.scalar(
            select(LegalIntake.id).where(LegalIntake.lead_id == lead.id).order_by(LegalIntake.created_at.desc()).limit(1)
        )
    message = CaseMessage(lead_id=lead.id, intake_id=intake_id, author="lawyer", channel="workspace", text=text)
    db.add(message)
    db.flush()
    write_audit(db, actor_type=ActorType.api_key, actor_id=identity.name, action="case_message.lawyer",
                target_type="lead", target_id=lead.id, details={"intake_id": str(intake_id) if intake_id else None})
    db.commit()
    db.refresh(message)

    delivered = ["cabinet"]
    token = telegram_delivery._client_token()
    if lead.telegram_user_id and token:
        markup = (
            json.dumps({"inline_keyboard": [[{"text": "✍️ Ответить по делу", "callback_data": f"case:{intake_id}"}]]})
            if intake_id else None
        )
        try:
            telegram_delivery.send(
                kind="case_reply",
                token=token,
                chat_id=lead.telegram_user_id,
                text=f"✉️ Ответ юриста по вашему обращению:\n\n{text}\n\nОтветить можно кнопкой ниже или в личном кабинете на сайте.",
                reply_markup=markup,
                retryable=True,
                lead_id=lead.id,
            )
            delivered.append("telegram")
        except Exception as exc:  # noqa: BLE001 — ответ уже в кабинете; повтор — из журнала отправок
            logger.warning("case reply telegram failed: %s", telegram_delivery.safe_error(exc))
    return {**_row(message), "delivered": delivered}


def unread_from_clients(db: Session) -> list[tuple[uuid.UUID, int, datetime]]:
    """Клиенты с непрочитанными юристом сообщениями — для «Задач»."""
    return list(db.execute(
        select(CaseMessage.lead_id, func.count(), func.max(CaseMessage.created_at))
        .where(CaseMessage.author == "client", CaseMessage.read_at.is_(None))
        .group_by(CaseMessage.lead_id)
        .order_by(func.max(CaseMessage.created_at))
    ).all())
