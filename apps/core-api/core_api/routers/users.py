from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.idempotency import cached_response, store_response
from core_api.models import ActorType, Event, Lead, Scope, User, UserRole
from core_api.schemas import UserCreate, UserDataOperationOut, UserOut, UserPatch

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
        cached = cached_response(db, idempotency_key, namespace="users.upsert")
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
            namespace="users.upsert",
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
    offset: int = 0,
) -> list[User]:
    _ = identity
    capped_limit = max(1, min(limit, 500))
    capped_offset = max(0, offset)
    query = select(User)
    if telegram_id is not None:
        query = query.where(User.telegram_id == telegram_id)
    if without_consent:
        query = query.where(User.consent_given.is_(False))
    if revoked_only:
        query = query.where(User.consent_revoked.is_(True))
    query = query.order_by(
        func.coalesce(User.last_interaction, User.created_at).desc(),
        User.created_at.desc(),
    ).offset(capped_offset).limit(capped_limit)
    return list(db.execute(query).scalars().all())


def _get_user_by_telegram_id(db: Session, telegram_id: int) -> User | None:
    return db.execute(select(User).where(User.telegram_id == telegram_id).limit(1)).scalar_one_or_none()


def _delete_events_for_telegram_user(db: Session, telegram_user_id: int, lead_ids: list[uuid.UUID], user_id: uuid.UUID) -> int:
    deleted = 0
    if lead_ids:
        deleted += db.execute(delete(Event).where(Event.lead_id.in_(lead_ids))).rowcount or 0

    deleted += db.execute(delete(Event).where(Event.user_id == user_id)).rowcount or 0

    # Cleanup events mirrored from legacy/user flows where telegram id is only in payload JSON.
    deleted += (
        db.execute(
            text(
                """
                DELETE FROM events
                WHERE (payload ->> 'telegram_user_id') = :tg_id
                   OR (payload ->> 'user_id') = :tg_id
                   OR (payload ->> 'telegram_id') = :tg_id
                """
            ),
            {"tg_id": str(int(telegram_user_id))},
        ).rowcount
        or 0
    )
    return int(deleted)


@router.post("/by-telegram/{telegram_user_id}/gdpr-clear", response_model=UserDataOperationOut)
def gdpr_clear_user_data(
    telegram_user_id: int,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> UserDataOperationOut:
    user = _get_user_by_telegram_id(db, telegram_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    user.consent_given = False
    user.consent_date = None
    user.consent_revoked = True
    user.consent_revoked_at = now
    user.transborder_consent = False
    user.transborder_consent_date = None
    user.marketing_consent = False
    user.marketing_consent_date = None
    user.last_interaction = now
    db.add(user)

    leads = list(db.execute(select(Lead).where(Lead.telegram_user_id == telegram_user_id)).scalars().all())
    leads_anonymized = 0
    for lead in leads:
        lead.name = "Анонимизировано"
        lead.contact = None
        lead.company = None
        lead.email = None
        lead.phone = None
        lead.notes = ((lead.notes or "").rstrip() + "\n[PDN] Анонимизировано по запросу пользователя")[-4000:]
        lead.updated_at = now
        db.add(lead)
        leads_anonymized += 1

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="user.gdpr_clear",
        target_type="user",
        target_id=user.id,
        details={"telegram_user_id": telegram_user_id, "leads_anonymized": leads_anonymized},
    )
    db.commit()
    return UserDataOperationOut(
        telegram_user_id=telegram_user_id,
        users_updated=1,
        leads_anonymized=leads_anonymized,
        messages_deleted=0,
    )


@router.post("/by-telegram/{telegram_user_id}/reset-new", response_model=UserDataOperationOut)
def reset_user_to_new(
    telegram_user_id: int,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> UserDataOperationOut:
    user = _get_user_by_telegram_id(db, telegram_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    lead_ids = list(
        db.execute(select(Lead.id).where(Lead.telegram_user_id == telegram_user_id)).scalars().all()
    )
    events_deleted = _delete_events_for_telegram_user(db, telegram_user_id, lead_ids, user.id)
    leads_deleted = db.execute(delete(Lead).where(Lead.telegram_user_id == telegram_user_id)).rowcount or 0

    user.consent_given = False
    user.consent_date = None
    user.consent_revoked = False
    user.consent_revoked_at = None
    user.transborder_consent = False
    user.transborder_consent_date = None
    user.marketing_consent = False
    user.marketing_consent_date = None
    user.conversation_stage = "discover"
    user.cta_variant = None
    user.cta_shown = False
    user.cta_shown_at = None
    user.last_interaction = now
    db.add(user)

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="user.reset_new",
        target_type="user",
        target_id=user.id,
        details={"telegram_user_id": telegram_user_id, "leads_deleted": int(leads_deleted), "events_deleted": events_deleted},
    )
    db.commit()
    return UserDataOperationOut(
        telegram_user_id=telegram_user_id,
        users_reset=1,
        leads_deleted=int(leads_deleted),
        events_deleted=events_deleted,
        messages_deleted=0,
    )


@router.delete("/by-telegram/{telegram_user_id}", response_model=UserDataOperationOut)
def delete_user_by_telegram(
    telegram_user_id: int,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> UserDataOperationOut:
    user = _get_user_by_telegram_id(db, telegram_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    lead_ids = list(
        db.execute(select(Lead.id).where(Lead.telegram_user_id == telegram_user_id)).scalars().all()
    )
    events_deleted = _delete_events_for_telegram_user(db, telegram_user_id, lead_ids, user.id)
    leads_deleted = db.execute(delete(Lead).where(Lead.telegram_user_id == telegram_user_id)).rowcount or 0
    users_deleted = db.execute(delete(User).where(User.id == user.id)).rowcount or 0

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="user.delete_by_telegram",
        target_type="user",
        target_id=user.id,
        details={"telegram_user_id": telegram_user_id, "leads_deleted": int(leads_deleted), "events_deleted": events_deleted},
    )
    db.commit()
    return UserDataOperationOut(
        telegram_user_id=telegram_user_id,
        users_deleted=int(users_deleted),
        leads_deleted=int(leads_deleted),
        events_deleted=events_deleted,
        messages_deleted=0,
    )


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
