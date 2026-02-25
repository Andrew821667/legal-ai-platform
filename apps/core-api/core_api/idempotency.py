from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core_api.models import IdempotencyKey
from core_api.security import hash_idempotency_key


def cached_response(db: Session, raw_key: str) -> tuple[int, dict[str, Any]] | None:
    key_hash = hash_idempotency_key(raw_key)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    stmt = select(IdempotencyKey).where(
        IdempotencyKey.key_hash == key_hash,
        IdempotencyKey.created_at >= cutoff,
    )
    record = db.execute(stmt).scalar_one_or_none()
    if record is None:
        return None
    return record.response_status, record.response_body


def store_response(db: Session, raw_key: str, status: int, body: dict[str, Any]) -> None:
    key_hash = hash_idempotency_key(raw_key)
    db.add(IdempotencyKey(key_hash=key_hash, response_status=status, response_body=body))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
