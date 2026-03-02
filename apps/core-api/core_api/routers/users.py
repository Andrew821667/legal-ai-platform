from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.idempotency import cached_response, store_response
from core_api.models import Scope, User, UserRole
from core_api.schemas import UserCreate, UserOut, UserPatch

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("", response_model=UserOut)
def upsert_user(
    payload: UserCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> User:
    _ = identity
    if idempotency_key:
        cached = cached_response(db, idempotency_key)
        if cached:
            cached_status, cached_body = cached
            return JSONResponse(status_code=cached_status, content=cached_body)

    user = None
    if payload.telegram_id is not None:
        user = db.execute(select(User).where(User.telegram_id == payload.telegram_id).limit(1)).scalar_one_or_none()

    if user is None:
        user = User(
            role=payload.role,
            telegram_id=payload.telegram_id,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            name=payload.name,
            consent_given=payload.consent_given,
            consent_date=payload.consent_date,
            consent_revoked=payload.consent_revoked,
            consent_revoked_at=payload.consent_revoked_at,
            transborder_consent=payload.transborder_consent,
            transborder_consent_date=payload.transborder_consent_date,
            marketing_consent=payload.marketing_consent,
            marketing_consent_date=payload.marketing_consent_date,
            conversation_stage=payload.conversation_stage,
            cta_variant=payload.cta_variant,
            cta_shown=payload.cta_shown,
            cta_shown_at=payload.cta_shown_at,
            last_interaction=payload.last_interaction or datetime.now(timezone.utc),
        )
        db.add(user)
    else:
        payload_data = payload.model_dump(exclude_none=True)
        for key, value in payload_data.items():
            setattr(user, key, value)
        if payload.last_interaction is None:
            user.last_interaction = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    if idempotency_key:
        store_response(
            db,
            idempotency_key,
            status.HTTP_200_OK,
            UserOut.model_validate(user).model_dump(mode="json"),
        )

    return user


@router.get("", response_model=list[UserOut])
def list_users(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
    telegram_id: int | None = None,
    without_consent: bool = False,
    revoked_only: bool = False,
    limit: int = 100,
) -> list[User]:
    _ = identity
    capped_limit = max(1, min(limit, 500))
    query = select(User)
    if telegram_id is not None:
        query = query.where(User.telegram_id == telegram_id)
    if without_consent:
        query = query.where(User.consent_given.is_(False))
    if revoked_only:
        query = query.where(User.consent_revoked.is_(True))
    query = query.order_by(func.coalesce(User.last_interaction, User.created_at).desc(), User.created_at.desc()).limit(
        capped_limit
    )
    return list(db.execute(query).scalars().all())


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> User:
    _ = identity
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def patch_user(
    user_id: uuid.UUID,
    payload: UserPatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> User:
    _ = identity
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(user, key, value)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user
