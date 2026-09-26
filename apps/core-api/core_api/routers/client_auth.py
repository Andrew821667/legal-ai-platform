"""Учётная запись клиента для входа в кабинет без Telegram.

Telegram в России заблокирован: «Войти через Telegram» без VPN не работает.
Вход через Яндекс ID проходит на сайте (OAuth с PKCE, обмен кода — на сервере
сайта); сюда сайт передаёт уже подтверждённые Яндексом id и почту, ядро
находит или заводит учётную запись. Ключ — бота: ядру доверяет только сайт.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.client_principal import normalize_email
from core_api.db import get_db
from core_api.models import ActorType, ClientAccount, Scope

router = APIRouter(prefix="/api/v1/client-auth", tags=["client-auth"])


class YandexLogin(BaseModel):
    yandex_id: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=5, max_length=254)
    display_name: str | None = Field(default=None, max_length=255)


def account_payload(account: ClientAccount) -> dict:
    return {
        "client_account_id": str(account.id),
        "email": account.email,
        "display_name": account.display_name,
        "telegram_user_id": account.telegram_user_id,
        "yandex": account.yandex_id is not None,
    }


@router.post("/yandex")
def yandex_login(
    payload: YandexLogin,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Находит учётную запись по Яндекс ID, иначе по почте, иначе заводит.

    Почта из Яндекса подтверждена самим Яндексом (default_email). Если у
    записи с этой почтой уже другой Яндекс ID — это другой человек или
    сменённый аккаунт: не сливаем молча.
    """
    email = normalize_email(payload.email)
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Invalid email")
    account = db.scalar(select(ClientAccount).where(ClientAccount.yandex_id == payload.yandex_id).with_for_update())
    created = False
    if account is None:
        account = db.scalar(select(ClientAccount).where(ClientAccount.email == email).with_for_update())
        if account is not None and account.yandex_id not in (None, payload.yandex_id):
            raise HTTPException(status_code=409, detail="Email is linked to another Yandex account")
        if account is None:
            account = ClientAccount(email=email)
            db.add(account)
            created = True
        account.yandex_id = payload.yandex_id
    elif account.email != email:
        # Сменил основную почту в Яндексе — берём новую, если она свободна.
        taken = db.scalar(select(ClientAccount.id).where(ClientAccount.email == email, ClientAccount.id != account.id))
        if taken is None:
            account.email = email
    if payload.display_name:
        account.display_name = payload.display_name.strip()[:255]
    account.last_login_at = datetime.now(timezone.utc)
    db.flush()
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="client_account.login",
        target_type="client_account",
        target_id=account.id,
        details={"method": "yandex", "created": created},
    )
    db.commit()
    return account_payload(account)


@router.get("/accounts/{account_id}")
def get_account(
    account_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    _ = identity
    account = db.get(ClientAccount, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Client account not found")
    return account_payload(account)
