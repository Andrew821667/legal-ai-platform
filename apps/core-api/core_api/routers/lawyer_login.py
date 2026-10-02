"""Погасить одноразовую ссылку входа в рабочее место юриста.

Подпись ссылки проверяет сайт (apps/web/lib/lawyer-login-token.ts) — у него
общий с ботом секрет. Ядро отвечает только за одно: чтобы ссылка сработала
один раз, даже если сайт перезапустился между двумя попытками.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import LawyerLoginNonce, Scope

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-workspace"])


class NonceIn(BaseModel):
    nonce: str = Field(pattern=r"^[0-9a-f]{32}$")
    telegram_user_id: int = Field(gt=0)
    expires_at: datetime


@router.post("/login-nonces", status_code=status.HTTP_201_CREATED)
def consume(
    payload: NonceIn,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """201 — ссылка погашена сейчас; 409 — уже была использована."""
    _ = identity
    now = datetime.now(timezone.utc)
    # Сроки истекли — строки больше ничего не защищают: подпись такой ссылки сайт и так отвергнет.
    db.execute(delete(LawyerLoginNonce).where(LawyerLoginNonce.expires_at < now))
    # RETURNING, а не rowcount: у ORM-вставки с ON CONFLICT rowcount = -1
    # и повтор от первой попытки не отличить.
    inserted = db.execute(
        insert(LawyerLoginNonce)
        .values(
            nonce_hash=hashlib.sha256(payload.nonce.encode("ascii")).hexdigest(),
            telegram_user_id=payload.telegram_user_id,
            expires_at=payload.expires_at,
        )
        .on_conflict_do_nothing(index_elements=["nonce_hash"])
        .returning(LawyerLoginNonce.nonce_hash)
    ).scalar_one_or_none()
    db.commit()
    if inserted is None:
        raise HTTPException(status_code=409, detail="Login link already used")
    return {"consumed": True}
