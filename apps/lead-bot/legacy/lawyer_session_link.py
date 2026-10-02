"""Ссылка для автономного входа в рабочее место — минуя Telegram.

Внутри Telegram initData приходит из inline-кнопки и кнопки меню — но не из
кнопки reply-клавиатуры: такой запуск Telegram оставляет без initData вовсе.
Вне Telegram (иконка на экране iPhone, обычная вкладка Safari) её нет тем
более. Обе эти двери бот открывает сам: подписанной ссылкой по запросу
владельца и такой же ссылкой в адресе нижней кнопки.

Ссылка одноразовая. Раньше в ней лежал сам токен сессии на 30 дней — она
открывалась сколько угодно раз и оседала в истории браузера и журналах.
Теперь в ней токен входа: короткий срок, случайный nonce, своя подпись.
Сайт (apps/web/lib/lawyer-login-token.ts) проверяет подпись, гасит nonce в
ядре и выдаёт свою куку сессии. Формат и подпись должны бит-в-бит совпадать
с сайтом: v2.<id>.<issuedAt>.<ttl>.<nonce>.<hex-hmac>, HMAC-SHA256 общим
секретом (LAWYER_SESSION_SECRET) над "lawyer-login.<id>.<issuedAt>.<ttl>.<nonce>".
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

# «Ссылка для Safari» — открыть сразу; нижняя кнопка живёт до следующего /admin.
SAFARI_LINK_TTL_SECONDS = 15 * 60
KEYBOARD_LINK_TTL_SECONDS = 7 * 24 * 60 * 60


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def mint_login_token(telegram_user_id: int, secret: str, *, ttl_seconds: int) -> str:
    """Одноразовый токен входа. Гасит его сайт при первом использовании."""
    payload = f"{telegram_user_id}.{int(time.time())}.{int(ttl_seconds)}.{secrets.token_hex(16)}"
    return f"v2.{payload}.{_sign(f'lawyer-login.{payload}', secret)}"


def build_login_url(
    telegram_user_id: int,
    *,
    workspace_url: str,
    secret: str,
    ttl_seconds: int = SAFARI_LINK_TTL_SECONDS,
) -> str | None:
    """Полная ссылка на /lawyer/login с одноразовым токеном.

    Возвращает None, если секрет не задан: выдавать ссылку, которую сервер
    не сможет проверить, хуже, чем не выдавать её вовсе.
    """
    if not secret or not workspace_url:
        return None
    origin = workspace_url.rstrip("/")
    # workspace_url обычно заканчивается на /lawyer — отрезаем последний
    # сегмент, чтобы не получить /lawyer/lawyer/login.
    if origin.endswith("/lawyer"):
        origin = origin[: -len("/lawyer")]
    token = mint_login_token(telegram_user_id, secret, ttl_seconds=ttl_seconds)
    return f"{origin}/lawyer/login?token={token}"
