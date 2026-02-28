from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.config import get_settings
from core_api.db import get_db
from core_api.models import ActorType, ScheduledPost, ScheduledPostStatus, Scope
from core_api.schemas import ScheduledPostCreate, ScheduledPostOut, ScheduledPostPatch

router = APIRouter(prefix="/api/v1/scheduled-posts", tags=["scheduled-posts"])


@router.post("", response_model=ScheduledPostOut)
def create_scheduled_post(
    payload: ScheduledPostCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.admin)),
    db: Session = Depends(get_db),
) -> ScheduledPost:
    _ = identity
    post = ScheduledPost(**payload.model_dump())
    db.add(post)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate source_hash")
    db.refresh(post)
    return post


@router.get("", response_model=list[ScheduledPostOut])
def list_scheduled_posts(
    due: bool = Query(default=False),
    status: ScheduledPostStatus | None = Query(default=None),
    newest_first: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[ScheduledPost]:
    _ = identity
    order_by = ScheduledPost.publish_at.desc() if newest_first else ScheduledPost.publish_at.asc()
    stmt = select(ScheduledPost).order_by(order_by).limit(limit)
    if status is not None:
        stmt = stmt.where(ScheduledPost.status == status)
    if due:
        stmt = stmt.where(
            and_(
                ScheduledPost.status == ScheduledPostStatus.scheduled,
                ScheduledPost.publish_at <= datetime.now(timezone.utc),
            )
        )
    return list(db.execute(stmt).scalars().all())


@router.post("/claim", response_model=list[ScheduledPostOut])
def claim_scheduled_posts(
    limit: int = Query(default=10, ge=1, le=50),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[ScheduledPost] | Response:
    now = datetime.now(timezone.utc)
    retry_failed_after = now - timedelta(minutes=get_settings().news_retry_failed_after_minutes)
    stmt = (
        select(ScheduledPost)
        .where(
            or_(
                and_(
                    ScheduledPost.status == ScheduledPostStatus.scheduled,
                    ScheduledPost.publish_at <= now,
                ),
                and_(
                    ScheduledPost.status == ScheduledPostStatus.failed,
                    ScheduledPost.attempts < ScheduledPost.max_attempts,
                    ScheduledPost.updated_at <= retry_failed_after,
                ),
            )
        )
        .order_by(ScheduledPost.publish_at.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
    )
    posts = list(db.execute(stmt).scalars().all())
    if not posts:
        db.commit()
        return Response(status_code=204)

    for post in posts:
        post.status = ScheduledPostStatus.publishing
        post.updated_at = now
        db.add(post)
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="post.claim",
            target_type="scheduled_post",
            target_id=post.id,
        )

    db.commit()
    for post in posts:
        db.refresh(post)
    return posts


@router.get("/{post_id}", response_model=ScheduledPostOut)
def get_scheduled_post(
    post_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.admin)),
    db: Session = Depends(get_db),
) -> ScheduledPost:
    _ = identity
    post = db.get(ScheduledPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.patch("/{post_id}", response_model=ScheduledPostOut)
def patch_scheduled_post(
    post_id: uuid.UUID,
    payload: ScheduledPostPatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.admin)),
    db: Session = Depends(get_db),
) -> ScheduledPost:
    post = db.get(ScheduledPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    prev_status = post.status

    if payload.title is not None:
        post.title = payload.title
    if payload.text is not None:
        post.text = payload.text
    if payload.publish_at is not None:
        post.publish_at = payload.publish_at

    if payload.status is not None:
        post.status = payload.status
        if payload.status == ScheduledPostStatus.posted:
            post.last_error = None
        elif payload.last_error is not None:
            post.last_error = payload.last_error
    elif payload.last_error is not None:
        post.last_error = payload.last_error

    post.updated_at = datetime.now(timezone.utc)
    if payload.status == ScheduledPostStatus.failed and prev_status != ScheduledPostStatus.failed:
        post.attempts += 1

    db.add(post)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="post.update",
        target_type="scheduled_post",
        target_id=post.id,
        details=payload.model_dump(exclude_none=True),
    )
    db.commit()
    db.refresh(post)
    return post


@router.post("/reset-stale", response_model=dict[str, int])
def reset_stale_scheduled_posts(
    older_than_minutes: int = Query(default=30, ge=1, le=240),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    _ = identity
    threshold = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    stale_rows = db.execute(
        select(ScheduledPost).where(
            ScheduledPost.status == ScheduledPostStatus.publishing,
            ScheduledPost.updated_at < threshold,
        )
    ).scalars().all()

    reset_count = 0
    for post in stale_rows:
        post.status = ScheduledPostStatus.failed
        if post.attempts < post.max_attempts:
            post.attempts += 1
        post.last_error = "stale publishing reset"
        post.updated_at = datetime.now(timezone.utc)
        db.add(post)
        write_audit(
            db,
            actor_type=ActorType.system,
            actor_id="cron.reset_stale_posts",
            action="post.reset_stale",
            target_type="scheduled_post",
            target_id=post.id,
        )
        reset_count += 1

    db.commit()
    return {"reset_count": reset_count}
