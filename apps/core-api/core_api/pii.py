"""Шифрование персональных данных на уровне приложения.

Реквизиты документа, удостоверяющего личность, нужны только для того, чтобы
подпись под NDA и согласие на обработку данных были привязаны к конкретному
человеку. Читать их надо редко и точечно; а лежат они в той же базе и в тех
же резервных копиях, что и всё остальное, на одном диске. Открытый текст
там означал бы, что любая утечка дампа — утечка паспортов.

Поэтому поле шифруется здесь, до базы: в PostgreSQL попадает только
токен Fernet (AES-128-CBC + HMAC, ключ из окружения). База и бэкапы без
ключа бесполезны, а код, которому реквизиты не нужны, их не видит вовсе —
SQLAlchemy расшифровывает при чтении столбца, и только там, где столбец
запрошен.

Ключ — PII_ENCRYPTION_KEY, стандартный ключ Fernet (32 байта, base64).
Без ключа записать поле нельзя: тихо сохранить паспорт открытым текстом
хуже, чем упасть. Прочитать значение, записанное до шифрования, можно —
префикс отличает токен от старого открытого текста, и миграция 0032
дошифровывает старые строки.
"""

from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

_PREFIX = "enc:v1:"


class PiiKeyMissingError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _fernet() -> Fernet | None:
    key = (os.getenv("PII_ENCRYPTION_KEY") or "").strip()
    if not key:
        return None
    return Fernet(key.encode("utf-8"))


def reset_key_cache() -> None:
    """Для тестов: ключ читается один раз за процесс."""
    _fernet.cache_clear()


def is_encrypted(value: str | None) -> bool:
    return bool(value) and str(value).startswith(_PREFIX)


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    if is_encrypted(value):
        return value
    fernet = _fernet()
    if fernet is None:
        raise PiiKeyMissingError(
            "PII_ENCRYPTION_KEY is not set: refusing to store personal data unencrypted"
        )
    return _PREFIX + fernet.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value: str | None) -> str | None:
    if value is None or not is_encrypted(value):
        # Старая строка, записанная до шифрования, — отдаём как есть, пока
        # миграция её не дошифровала.
        return value
    fernet = _fernet()
    if fernet is None:
        raise PiiKeyMissingError("PII_ENCRYPTION_KEY is not set: cannot read encrypted personal data")
    token = value[len(_PREFIX) :].encode("ascii")
    try:
        return fernet.decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise PiiKeyMissingError("PII_ENCRYPTION_KEY does not match the stored data") from exc


class EncryptedText(TypeDecorator):
    """Столбец, который в базе всегда зашифрован, а в коде — обычная строка."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(value)

    def process_result_value(self, value, dialect):
        return decrypt(value)
