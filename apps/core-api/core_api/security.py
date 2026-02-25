from __future__ import annotations

import hashlib
import secrets

import bcrypt


def hash_api_key(raw_key: str) -> str:
    return bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    try:
        return bcrypt.checkpw(raw_key.encode("utf-8"), key_hash.encode("utf-8"))
    except ValueError:
        return False


def generate_api_key() -> str:
    return f"ak_{secrets.token_urlsafe(24)}"


def hash_idempotency_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
