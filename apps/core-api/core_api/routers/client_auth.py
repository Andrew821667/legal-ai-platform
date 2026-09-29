"""Учётная запись клиента для входа в кабинет без Telegram.

Telegram в России заблокирован: «Войти через Telegram» без VPN не работает.
Вход через Яндекс ID проходит на сайте (OAuth с PKCE, обмен кода — на сервере
сайта); сюда сайт передаёт уже подтверждённые Яндексом id и почту, ядро
находит или заводит учётную запись. Ключ — бота: ядру доверяет только сайт.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.client_principal import normalize_email
from core_api.db import get_db
from core_api.models import ActorType, ClientAccount, ClientLinkCode, Scope

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
        "telegram_username": account.telegram_username,
        "telegram_linked_at": account.telegram_linked_at.isoformat() if account.telegram_linked_at else None,
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


# --- Объединение с Telegram --------------------------------------------------
#
# Клиент вёл дела в Telegram-боте, а на сайт вошёл через Яндекс ID — кабинет
# пуст. Объединяем только по его согласию и с доказательством владения обоими
# входами:
#   • код: бот выдаёт одноразовый код тому, кто написал ему со своего
#     Telegram, клиент вводит его в кабинете, вошедши через Яндекс ID;
#   • обе сессии: в одном браузере клиент вошёл и через Telegram, и через
#     Яндекс ID — обе подписи проверил сайт.
# Направление важно: код рождается в Telegram и вводится на сайте. Обратное
# (ссылка с сайта, «подтвердите в боте») фишингуется одной кнопкой: чужой
# прислал бы ссылку, и владелец Telegram открыл бы ему свои дела.

LINK_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # без 0/O, 1/I/L
LINK_CODE_LENGTH = 8  # ~40 бит: перебор за 10 минут невозможен и без лимита
LINK_CODE_TTL = timedelta(minutes=10)


def normalize_link_code(value: str) -> str:
    return "".join(ch for ch in (value or "").upper() if ch in LINK_CODE_ALPHABET)


def link_code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("ascii")).hexdigest()


def mask_email(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def _clean_username(value: str | None) -> str | None:
    cleaned = (value or "").strip().lstrip("@")[:255]
    return cleaned or None


class LinkCodeIn(BaseModel):
    telegram_user_id: int = Field(gt=0)
    telegram_username: str | None = Field(default=None, max_length=255)


@router.post("/telegram-link-codes")
def issue_link_code(
    payload: LinkCodeIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Бот просит код для владельца Telegram. Прежние коды этого Telegram гаснут."""
    linked = db.scalar(select(ClientAccount).where(ClientAccount.telegram_user_id == payload.telegram_user_id))
    if linked is not None:
        return {"linked": True, "email_masked": mask_email(linked.email)}
    now = datetime.now(timezone.utc)
    db.execute(
        delete(ClientLinkCode).where(
            or_(ClientLinkCode.expires_at <= now, ClientLinkCode.telegram_user_id == payload.telegram_user_id)
        )
    )
    code = "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(LINK_CODE_LENGTH))
    row = ClientLinkCode(
        telegram_user_id=payload.telegram_user_id,
        telegram_username=_clean_username(payload.telegram_username),
        code_hash=link_code_hash(code),
        expires_at=now + LINK_CODE_TTL,
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="client_account.link_code_issued",
        target_type="client_link_code",
        target_id=row.id,
        details={},
    )
    db.commit()
    return {
        "linked": False,
        "code": f"{code[:4]}-{code[4:]}",
        "expires_at": row.expires_at.isoformat(),
        "ttl_minutes": int(LINK_CODE_TTL.total_seconds() // 60),
    }


class LinkTelegramIn(BaseModel):
    """Ровно одно: код из бота или Telegram, чью сессию в том же браузере проверил сайт."""

    code: str | None = Field(default=None, max_length=32)
    telegram_user_id: int | None = Field(default=None, gt=0)
    telegram_username: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _one_of(self) -> LinkTelegramIn:
        if (self.code is None) == (self.telegram_user_id is None):
            raise ValueError("code or telegram_user_id is required")
        return self


def _locked_account(db: Session, account_id: uuid.UUID) -> ClientAccount:
    account = db.scalar(select(ClientAccount).where(ClientAccount.id == account_id).with_for_update())
    if account is None:
        raise HTTPException(status_code=404, detail="Client account not found")
    return account


@router.post("/accounts/{account_id}/telegram")
def link_telegram(
    account_id: uuid.UUID,
    payload: LinkTelegramIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Привязывает Telegram к учётной записи. Чужой Telegram не перехватывает."""
    account = _locked_account(db, account_id)
    if payload.code is not None:
        code = normalize_link_code(payload.code)
        row = None
        if len(code) == LINK_CODE_LENGTH:
            row = db.scalar(
                select(ClientLinkCode)
                .where(ClientLinkCode.code_hash == link_code_hash(code), ClientLinkCode.expires_at > datetime.now(timezone.utc))
                .with_for_update()
            )
        if row is None:
            raise HTTPException(status_code=400, detail="invalid_code")
        telegram_user_id, username, method = row.telegram_user_id, row.telegram_username, "bot_code"
        db.delete(row)
    else:
        telegram_user_id = payload.telegram_user_id
        username, method = _clean_username(payload.telegram_username), "site_sessions"

    if account.telegram_user_id == telegram_user_id:
        db.commit()
        return account_payload(account)
    if account.telegram_user_id is not None:
        raise HTTPException(status_code=409, detail="account_has_other_telegram")
    taken = db.scalar(select(ClientAccount.id).where(ClientAccount.telegram_user_id == telegram_user_id))
    if taken is not None:
        raise HTTPException(status_code=409, detail="telegram_linked_elsewhere")

    account.telegram_user_id = telegram_user_id
    account.telegram_username = username
    account.telegram_linked_at = datetime.now(timezone.utc)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="client_account.telegram_linked",
        target_type="client_account",
        target_id=account.id,
        details={"method": method},
    )
    try:
        db.commit()
    except IntegrityError as exc:  # тот же Telegram привязали параллельно
        db.rollback()
        raise HTTPException(status_code=409, detail="telegram_linked_elsewhere") from exc
    return account_payload(account)


@router.delete("/accounts/{account_id}/telegram")
def unlink_telegram(
    account_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Отзыв согласия: учётная запись снова видит только дела с сайта."""
    account = _locked_account(db, account_id)
    if account.telegram_user_id is not None:
        account.telegram_user_id = None
        account.telegram_username = None
        account.telegram_linked_at = None
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="client_account.telegram_unlinked",
            target_type="client_account",
            target_id=account.id,
            details={},
        )
    db.commit()
    return account_payload(account)
