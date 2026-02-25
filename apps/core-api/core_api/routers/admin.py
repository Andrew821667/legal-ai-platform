from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, cache, require_scopes
from core_api.db import get_db
from core_api.models import ActorType, ApiKey, Scope
from core_api.schemas import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyOut, MessageResponse
from core_api.security import generate_api_key, hash_api_key

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> list[ApiKey]:
    _ = identity
    return list(db.execute(select(ApiKey).order_by(ApiKey.created_at.desc())).scalars().all())


@router.post("/api-keys", response_model=ApiKeyCreateResponse)
def create_api_key(
    payload: ApiKeyCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> ApiKeyCreateResponse:
    plain_key = generate_api_key()
    row = ApiKey(name=payload.name, scope=payload.scope, key_hash=hash_api_key(plain_key))
    db.add(row)
    db.flush()

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="api_key.create",
        target_type="api_key",
        target_id=row.id,
        details={"name": payload.name, "scope": payload.scope.value},
    )

    db.commit()
    db.refresh(row)
    cache.invalidate()
    return ApiKeyCreateResponse(id=row.id, name=row.name, scope=row.scope, api_key=plain_key)


@router.delete("/api-keys/{key_id}", response_model=MessageResponse)
def revoke_api_key(
    key_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    row = db.get(ApiKey, key_id)
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")

    row.is_active = False
    db.add(row)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="api_key.revoke",
        target_type="api_key",
        target_id=row.id,
    )
    db.commit()
    cache.invalidate()
    return MessageResponse(message="revoked")
