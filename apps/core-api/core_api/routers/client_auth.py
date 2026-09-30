"""Учётная запись клиента для входа в кабинет без Telegram.

Telegram в России заблокирован: «Войти через Telegram» без VPN не работает.
Вход через Яндекс ID проходит на сайте (OAuth с PKCE, обмен кода — на сервере
сайта); сюда сайт передаёт уже подтверждённые Яндексом id и почту, ядро
находит или заводит учётную запись. Ключ — бота: ядру доверяет только сайт.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core_api import telegram_delivery
from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.client_principal import normalize_email
from core_api.db import get_db
from core_api.lead_notifications import _post_telegram_message
from core_api.models import ActorType, ClientAccount, ClientLinkCode, Scope

logger = logging.getLogger(__name__)

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
    pending = db.scalar(
        select(ClientLinkCode.id).where(
            ClientLinkCode.claimed_account_id == account.id, ClientLinkCode.expires_at > datetime.now(timezone.utc)
        )
    )
    return {**account_payload(account), "link_pending": pending is not None}


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
# И код не объединяет сразу: бот показывает владельцу Telegram почту учётной
# записи и спрашивает «Объединить?» — объединяем только после «Да». Иначе
# человек не видит, с чем объединился (почта Яндекса бывает не той, что он ждёт).

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


def _tell_telegram(kind: str, chat_id: int, text: str, reply_markup: str | None = None, *, retryable: bool) -> None:
    """Сообщение владельцу Telegram через бота-ассистента; исход — в журнале отправок."""
    token = telegram_delivery._client_token()
    if not token:
        raise RuntimeError("client bot token is not configured")
    telegram_delivery.send(
        kind=kind,
        token=token,
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        retryable=retryable,
        transport=_post_telegram_message,
    )


def confirmation_text(email: str) -> str:
    return (
        "🔗 Объединить ваш Telegram с учётной записью на сайте ai-verdict.ru?\n\n"
        f"Почта учётной записи: {email}\n\n"
        "После объединения в кабинете на сайте будут видны ваши дела и документы из Telegram, "
        "а здесь — заявки с сайта.\n\n"
        "Если это не ваша почта или код на сайте вводили не вы — нажмите «Нет, это не я»."
    )


def confirmation_markup(code_id: uuid.UUID) -> str:
    return json.dumps(
        {
            "inline_keyboard": [
                [{"text": "✅ Да, объединить", "callback_data": f"clink:ok:{code_id}"}],
                [{"text": "❌ Нет, это не я", "callback_data": f"clink:no:{code_id}"}],
            ]
        },
        ensure_ascii=False,
    )


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


def _already_linked(db: Session, account: ClientAccount, telegram_user_id: int) -> bool:
    """True — к записи уже привязан этот Telegram; чужой перехватить нельзя (409)."""
    if account.telegram_user_id == telegram_user_id:
        return True
    if account.telegram_user_id is not None:
        raise HTTPException(status_code=409, detail="account_has_other_telegram")
    taken = db.scalar(select(ClientAccount.id).where(ClientAccount.telegram_user_id == telegram_user_id))
    if taken is not None:
        raise HTTPException(status_code=409, detail="telegram_linked_elsewhere")
    return False


def _audit(db: Session, identity: ApiKeyIdentity, account: ClientAccount, action: str, details: dict) -> None:
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action=action,
        target_type="client_account",
        target_id=account.id,
        details=details,
    )


def _link(
    db: Session,
    identity: ApiKeyIdentity,
    account: ClientAccount,
    telegram_user_id: int,
    username: str | None,
    method: str,
) -> None:
    account.telegram_user_id = telegram_user_id
    account.telegram_username = username
    account.telegram_linked_at = datetime.now(timezone.utc)
    _audit(db, identity, account, "client_account.telegram_linked", {"method": method})
    try:
        db.commit()
    except IntegrityError as exc:  # тот же Telegram привязали параллельно
        db.rollback()
        raise HTTPException(status_code=409, detail="telegram_linked_elsewhere") from exc


def notice_text(email: str) -> str:
    return (
        "🔗 Ваш Telegram объединён с учётной записью на сайте ai-verdict.ru.\n\n"
        f"Почта учётной записи: {email}\n\n"
        "Если это были не вы — нажмите «Отвязать»."
    )


def undo_markup(account_id: uuid.UUID) -> str:
    return json.dumps(
        {"inline_keyboard": [[{"text": "Отвязать", "callback_data": f"clink:undo:{account_id}"}]]},
        ensure_ascii=False,
    )


@router.post("/accounts/{account_id}/telegram")
def link_telegram(
    account_id: uuid.UUID,
    payload: LinkTelegramIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Код из бота — запрос «Объединить?» владельцу Telegram (ответ — decision);
    две свежие сессии — объединение сразу и уведомление в Telegram с «Отвязать»."""
    account = _locked_account(db, account_id)
    now = datetime.now(timezone.utc)
    if payload.code is not None:
        code = normalize_link_code(payload.code)
        row = None
        if len(code) == LINK_CODE_LENGTH:
            row = db.scalar(
                select(ClientLinkCode)
                .where(ClientLinkCode.code_hash == link_code_hash(code), ClientLinkCode.expires_at > now)
                .with_for_update()
            )
        if row is None or row.claimed_account_id not in (None, account.id):
            raise HTTPException(status_code=400, detail="invalid_code")
        if _already_linked(db, account, row.telegram_user_id):
            db.delete(row)
            db.commit()
            return {**account_payload(account), "pending": False}
        row.claimed_account_id = account.id
        row.claimed_at = now
        row.expires_at = now + LINK_CODE_TTL
        db.flush()
        try:
            _tell_telegram(
                "link_confirm",
                row.telegram_user_id,
                confirmation_text(account.email),
                confirmation_markup(row.id),
                retryable=False,
            )
        except Exception as exc:  # noqa: BLE001 — исход уже в журнале отправок
            db.rollback()
            logger.warning("link confirmation was not delivered: %s", telegram_delivery.safe_error(exc))
            raise HTTPException(status_code=502, detail="telegram_unavailable") from exc
        _audit(db, identity, account, "client_account.link_requested", {})
        db.commit()
        return {**account_payload(account), "pending": True}

    telegram_user_id = payload.telegram_user_id
    if not _already_linked(db, account, telegram_user_id):
        _link(db, identity, account, telegram_user_id, _clean_username(payload.telegram_username), "site_sessions")
        try:
            _tell_telegram("link_notice", telegram_user_id, notice_text(account.email), undo_markup(account.id), retryable=True)
        except Exception as exc:  # noqa: BLE001 — уведомление повторит фон, объединение уже есть
            logger.warning("link notice was not delivered: %s", telegram_delivery.safe_error(exc))
    else:
        db.commit()
    return {**account_payload(account), "pending": False}


class LinkDecisionIn(BaseModel):
    telegram_user_id: int = Field(gt=0)
    accept: bool


@router.post("/telegram-link-codes/{code_id}/decision")
def decide_link(
    code_id: uuid.UUID,
    payload: LinkDecisionIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Ответ владельца Telegram на «Объединить?» — кнопка в боте. Решает только он."""
    row = db.scalar(select(ClientLinkCode).where(ClientLinkCode.id == code_id).with_for_update())
    if (
        row is None
        or row.telegram_user_id != payload.telegram_user_id
        or row.claimed_account_id is None
        or row.expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=410, detail="link_request_expired")
    account = _locked_account(db, row.claimed_account_id)
    if not payload.accept:
        db.delete(row)
        _audit(db, identity, account, "client_account.link_declined", {})
        db.commit()
        return {"status": "declined", "email": account.email}
    already = _already_linked(db, account, row.telegram_user_id)
    telegram_user_id, username = row.telegram_user_id, row.telegram_username
    db.delete(row)
    if already:
        db.commit()
    else:
        _link(db, identity, account, telegram_user_id, username, "bot_code")
    return {"status": "linked", "email": account.email}


def _unlink(db: Session, identity: ApiKeyIdentity, account: ClientAccount, by: str) -> None:
    if account.telegram_user_id is not None:
        account.telegram_user_id = None
        account.telegram_username = None
        account.telegram_linked_at = None
        _audit(db, identity, account, "client_account.telegram_unlinked", {"by": by})
    db.commit()


@router.delete("/accounts/{account_id}/telegram")
def unlink_telegram(
    account_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Отзыв согласия в кабинете: учётная запись снова видит только дела с сайта."""
    account = _locked_account(db, account_id)
    _unlink(db, identity, account, "site")
    return account_payload(account)


class OwnerUnlinkIn(BaseModel):
    telegram_user_id: int = Field(gt=0)


@router.post("/accounts/{account_id}/telegram/owner-unlink")
def owner_unlink(
    account_id: uuid.UUID,
    payload: OwnerUnlinkIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """«Это был не я» — владелец Telegram отвязывает его кнопкой в боте."""
    account = _locked_account(db, account_id)
    if account.telegram_user_id != payload.telegram_user_id:
        raise HTTPException(status_code=403, detail="Telegram is not linked to this account")
    _unlink(db, identity, account, "telegram")
    return {"status": "unlinked", "email": account.email}
