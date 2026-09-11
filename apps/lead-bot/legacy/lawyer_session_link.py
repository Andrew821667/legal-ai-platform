"""Ссылка для автономного входа в рабочее место — минуя Telegram.

Внутри Telegram initData приходит из inline-кнопки и кнопки меню — но не из
кнопки reply-клавиатуры: такой запуск Telegram оставляет без initData вовсе.
Вне Telegram (иконка на экране iPhone, обычная вкладка Safari) её нет тем
более. Обе эти двери бот открывает сам: подписанной ссылкой по запросу
владельца и тем же токеном в адресе нижней кнопки.

Формат токена и подпись должны бит-в-бит совпадать с тем, что проверяет
apps/web/lib/lawyer-session-token.ts — это одна и та же схема, реализованная
дважды на двух языках, потому что состояние нигде не хранится: секрет общий
(LAWYER_SESSION_SECRET, один и тот же .env для обоих сервисов), а проверка —
это пересчитать HMAC и сравнить.
"""

from __future__ import annotations

import hashlib
import hmac
import time


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def mint_session_token(telegram_user_id: int, secret: str) -> str:
    """Собирает подписанный токен. Состояния на сервере не остаётся."""
    payload = f"{telegram_user_id}.{int(time.time())}"
    return f"{payload}.{_sign(payload, secret)}"


def build_login_url(telegram_user_id: int, *, workspace_url: str, secret: str) -> str | None:
    """Полная ссылка на /lawyer/login с токеном.

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
    token = mint_session_token(telegram_user_id, secret)
    return f"{origin}/lawyer/login?token={token}"
