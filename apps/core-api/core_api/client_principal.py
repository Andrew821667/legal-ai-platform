"""Кто клиент — по Telegram или по учётной записи (email).

Раньше клиент везде был числом Telegram ID: сводка кабинета, подпись
договора, акты, NDA. Telegram в России заблокирован, и клиент без VPN не мог
ни войти, ни получить документы. Теперь сайт присылает либо telegram_user_id
(мини-апп, вход через Telegram), либо client_account_id (вход через
Яндекс ID), а здесь — единственное место, где решается, какие дела клиенту
видны и чей это документ.

Граница доступа по email: только к делам БЕЗ Telegram — заявкам с сайта, где
почту указал сам заявитель. Иначе человек, вписавший в боте чужую почту,
открыл бы её владельцу свои договоры с паспортными данными. Дела из Telegram
видны по почте, только если учётная запись привязана к тому же Telegram.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from core_api.models import ClientAccount, Lead


class ClientRef(BaseModel):
    """Кто действует: один из двух идентификаторов, их присылает сайт или бот."""

    telegram_user_id: int | None = Field(default=None, gt=0)
    client_account_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _one_of(self) -> ClientRef:
        if self.telegram_user_id is None and self.client_account_id is None:
            raise ValueError("telegram_user_id or client_account_id is required")
        return self


@dataclass(frozen=True)
class Principal:
    telegram_user_id: int | None
    account_id: uuid.UUID | None
    email: str | None
    lead_ids: frozenset[uuid.UUID]

    @property
    def via_email(self) -> bool:
        """Вошёл по почте и Telegram к учётной записи не привязан."""
        return self.account_id is not None and self.telegram_user_id is None

    def owns(self, *, lead_id: uuid.UUID | None, client_telegram_user_id: int | None) -> bool:
        """Документ клиента: адресован его Telegram или лежит в его деле без Telegram."""
        if self.telegram_user_id is not None and client_telegram_user_id == self.telegram_user_id:
            return True
        return client_telegram_user_id is None and lead_id is not None and lead_id in self.lead_ids


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def lead_filter(telegram_user_id: int | None, email: str | None):
    conditions = []
    if telegram_user_id is not None:
        conditions.append(Lead.telegram_user_id == telegram_user_id)
    if email:
        conditions.append(
            and_(
                Lead.telegram_user_id.is_(None),
                or_(func.lower(Lead.email) == email, func.lower(func.trim(Lead.contact)) == email),
            )
        )
    return or_(*conditions) if conditions else None


def resolve(
    db: Session,
    *,
    telegram_user_id: int | None = None,
    client_account_id: uuid.UUID | None = None,
) -> Principal:
    email: str | None = None
    if client_account_id is not None:
        account = db.get(ClientAccount, client_account_id)
        if account is None:
            raise HTTPException(status_code=401, detail="Client account not found")
        telegram_user_id = account.telegram_user_id
        email = account.email
    elif telegram_user_id is None:
        raise HTTPException(status_code=400, detail="telegram_user_id or client_account_id is required")
    condition = lead_filter(telegram_user_id, email)
    lead_ids = frozenset(db.scalars(select(Lead.id).where(condition))) if condition is not None else frozenset()
    return Principal(
        telegram_user_id=telegram_user_id,
        account_id=client_account_id,
        email=email,
        lead_ids=lead_ids,
    )


def resolve_ref(db: Session, ref: ClientRef) -> Principal:
    return resolve(db, telegram_user_id=ref.telegram_user_id, client_account_id=ref.client_account_id)
