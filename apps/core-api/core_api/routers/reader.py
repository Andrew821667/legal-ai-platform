from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import (
    ActorType,
    Event,
    Lead,
    LeadSource,
    LeadStatus,
    PostFeedbackSignal,
    PostFeedbackSource,
    ReaderPreference,
    ReaderSavedPost,
    ScheduledPost,
    ScheduledPostStatus,
    Scope,
)
from core_api.post_feedback import apply_feedback_signal
from core_api.schemas import (
    MessageResponse,
    PostFeedbackOut,
    ReaderCtaClickCreate,
    ReaderFeedItem,
    ReaderFeedbackCreate,
    ReaderLeadIntentCreate,
    ReaderLeadIntentOut,
    ReaderPreferencesOut,
    ReaderPreferencesPatch,
    ReaderSaveRequest,
    ReaderSaveResponse,
)

router = APIRouter(prefix="/api/v1/reader", tags=["reader"])

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "gdpr": ["gdpr", "персональн", "пдн", "privacy", "data protection"],
    "ai_law": ["искусственн", "нейросет", "ai", "llm", "ai act", "машинн"],
    "contracts": ["договор", "contract", "clm", "redline", "nda"],
    "compliance": ["комплаенс", "compliance", "санкц", "aml", "due diligence"],
    "litigation": ["суд", "litigation", "арбитраж", "dispute", "претензи"],
    "legal_ops": ["legal ops", "автоматизац", "workflow", "инхаус", "ops"],
    "privacy": ["privacy", "персональн", "transborder", "cross-border", "data transfer"],
    "regulation": ["regulation", "регулирован", "закон", "надзор", "policy"],
    "ai_general": ["ai", "llm", "agent", "copilot", "foundation model"],
}


def _normalize_topics(topics: list[str] | None) -> list[str]:
    if not topics:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in topics:
        normalized = str(item or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized[:64])
    return result[:30]


def _pref_for_user(db: Session, telegram_user_id: int) -> ReaderPreference | None:
    return db.execute(
        select(ReaderPreference).where(ReaderPreference.telegram_user_id == telegram_user_id).limit(1)
    ).scalar_one_or_none()


def _topic_score(post: ScheduledPost, topics: list[str]) -> int:
    if not topics:
        return 0
    haystack = f"{post.title or ''} {post.text or ''} {post.rubric or ''}".lower()
    score = 0
    for topic in topics:
        if topic and topic in (post.rubric or "").lower():
            score += 5
        for kw in _TOPIC_KEYWORDS.get(topic, []):
            if kw in haystack:
                score += 2
                break
    return score


def _feedback_score(post: ScheduledPost) -> int:
    snapshot = post.feedback_snapshot or {}
    try:
        value = int(snapshot.get("score", 0))
    except (TypeError, ValueError):
        value = 0
    return max(-100, min(value, 100))


def _feed_item(post: ScheduledPost, *, is_saved: bool) -> ReaderFeedItem:
    return ReaderFeedItem(
        id=post.id,
        title=post.title,
        text=post.text,
        source_url=post.source_url,
        rubric=post.rubric,
        format_type=post.format_type,
        cta_type=post.cta_type,
        publish_at=post.publish_at,
        posted_at=post.posted_at,
        feedback_snapshot=post.feedback_snapshot,
        is_saved=is_saved,
    )


@router.patch("/preferences", response_model=ReaderPreferencesOut)
def patch_reader_preferences(
    payload: ReaderPreferencesPatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> ReaderPreference:
    row = _pref_for_user(db, payload.telegram_user_id)
    if row is None:
        row = ReaderPreference(
            telegram_user_id=payload.telegram_user_id,
            topics=[],
            digest_frequency="never",
        )

    if payload.topics is not None:
        row.topics = _normalize_topics(payload.topics)
    if payload.digest_frequency is not None:
        row.digest_frequency = str(payload.digest_frequency or "never").strip()[:50] or "never"
    if payload.expertise_level is not None:
        row.expertise_level = str(payload.expertise_level or "").strip()[:50] or None

    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="reader.preferences.patch",
        target_type="reader_preference",
        target_id=row.id,
        details={"telegram_user_id": row.telegram_user_id},
    )
    db.commit()
    return row


@router.get("/feed", response_model=list[ReaderFeedItem])
def reader_feed(
    telegram_user_id: int = Query(ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    days: int = Query(default=14, ge=1, le=90),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[ReaderFeedItem]:
    _ = identity
    since = datetime.now(timezone.utc) - timedelta(days=days)
    pref = _pref_for_user(db, telegram_user_id)
    topics = _normalize_topics((pref.topics if pref else []) or [])

    candidates = list(
        db.execute(
            select(ScheduledPost)
            .where(
                and_(
                    ScheduledPost.status == ScheduledPostStatus.posted,
                    ScheduledPost.publish_at >= since,
                )
            )
            .order_by(ScheduledPost.publish_at.desc())
            .limit(max(limit * 8, 80))
        ).scalars().all()
    )
    if not candidates:
        return []

    saved_post_ids = {
        row.post_id
        for row in db.execute(
            select(ReaderSavedPost).where(ReaderSavedPost.telegram_user_id == telegram_user_id)
        ).scalars().all()
    }

    ranked = sorted(
        candidates,
        key=lambda post: (
            _topic_score(post, topics),
            _feedback_score(post),
            post.publish_at,
        ),
        reverse=True,
    )[:limit]

    return [_feed_item(post, is_saved=post.id in saved_post_ids) for post in ranked]


@router.get("/saved", response_model=list[ReaderFeedItem])
def reader_saved(
    telegram_user_id: int = Query(ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[ReaderFeedItem]:
    _ = identity
    saved_rows = list(
        db.execute(
            select(ReaderSavedPost)
            .where(ReaderSavedPost.telegram_user_id == telegram_user_id)
            .order_by(ReaderSavedPost.created_at.desc())
            .limit(limit)
        ).scalars().all()
    )
    if not saved_rows:
        return []

    post_ids = [row.post_id for row in saved_rows]
    posts = {
        row.id: row
        for row in db.execute(
            select(ScheduledPost).where(
                and_(
                    ScheduledPost.id.in_(post_ids),
                    ScheduledPost.status == ScheduledPostStatus.posted,
                )
            )
        ).scalars().all()
    }

    result: list[ReaderFeedItem] = []
    for row in saved_rows:
        post = posts.get(row.post_id)
        if post is None:
            continue
        result.append(_feed_item(post, is_saved=True))
    return result


@router.post("/save", response_model=ReaderSaveResponse)
def reader_save(
    payload: ReaderSaveRequest,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> ReaderSaveResponse:
    _ = identity
    post = db.get(ScheduledPost, payload.post_id)
    if post is None or post.status != ScheduledPostStatus.posted:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = db.execute(
        select(ReaderSavedPost)
        .where(ReaderSavedPost.telegram_user_id == payload.telegram_user_id)
        .where(ReaderSavedPost.post_id == payload.post_id)
        .limit(1)
    ).scalar_one_or_none()

    if payload.saved:
        if existing is None:
            db.add(ReaderSavedPost(telegram_user_id=payload.telegram_user_id, post_id=payload.post_id))
            db.commit()
        return ReaderSaveResponse(post_id=payload.post_id, saved=True)

    if existing is not None:
        db.delete(existing)
        db.commit()
    return ReaderSaveResponse(post_id=payload.post_id, saved=False)


@router.post("/feedback", response_model=PostFeedbackOut)
def reader_feedback(
    payload: ReaderFeedbackCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> PostFeedbackSignal:
    _ = identity
    post = db.get(ScheduledPost, payload.post_id)
    if post is None or post.status != ScheduledPostStatus.posted:
        raise HTTPException(status_code=404, detail="Post not found")

    now = datetime.now(timezone.utc)
    signal = PostFeedbackSignal(
        post_id=payload.post_id,
        source=PostFeedbackSource.comment,
        signal_key=payload.signal_key,
        signal_value=payload.signal_value,
        text=payload.text,
        telegram_user_id=payload.telegram_user_id,
        actor_name="reader_api",
        payload=payload.payload,
    )
    db.add(signal)
    db.flush()

    post.feedback_snapshot = apply_feedback_signal(
        post.feedback_snapshot,
        source=PostFeedbackSource.comment.value,
        signal_value=payload.signal_value,
        text=payload.text,
        payload=payload.payload,
        created_at_iso=now.isoformat(),
    )
    post.updated_at = now
    db.add(post)
    db.commit()
    db.refresh(signal)
    return signal


@router.post("/cta-click", response_model=MessageResponse)
def reader_cta_click(
    payload: ReaderCtaClickCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    _ = identity
    db.add(
        Event(
            lead_id=None,
            user_id=None,
            type="reader.cta_click",
            payload={
                "telegram_user_id": payload.telegram_user_id,
                "post_id": str(payload.post_id) if payload.post_id else None,
                "cta_type": payload.cta_type,
                "context": payload.context,
                "payload": payload.payload,
            },
        )
    )
    db.commit()
    return MessageResponse(message="ok")


@router.post("/lead-intent", response_model=ReaderLeadIntentOut)
def reader_lead_intent(
    payload: ReaderLeadIntentCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> ReaderLeadIntentOut:
    _ = identity
    lead = db.execute(
        select(Lead)
        .where(Lead.telegram_user_id == payload.telegram_user_id)
        .order_by(Lead.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    created = False
    now = datetime.now(timezone.utc)
    if lead is None:
        lead = Lead(
            source=LeadSource.telegram_channel,
            telegram_user_id=payload.telegram_user_id,
            name=payload.name,
            contact=payload.contact,
            status=LeadStatus.new,
            cta_variant="reader_referral",
            notes=f"[READER_REFERRAL] intent={payload.intent_type}",
            last_activity_at=now,
        )
        db.add(lead)
        db.flush()
        created = True
    else:
        lead.last_activity_at = now
        if payload.contact and not lead.contact:
            lead.contact = payload.contact
        if payload.name and not lead.name:
            lead.name = payload.name
        note_suffix = f"\n[READER_REFERRAL] intent={payload.intent_type}"
        current_notes = lead.notes or ""
        lead.notes = (current_notes + note_suffix)[-4000:]
        db.add(lead)

    db.add(
        Event(
            lead_id=lead.id,
            user_id=None,
            type="reader.lead_intent",
            payload={
                "telegram_user_id": payload.telegram_user_id,
                "post_id": str(payload.post_id) if payload.post_id else None,
                "intent_type": payload.intent_type,
                "message": payload.message,
                "payload": payload.payload,
            },
        )
    )
    db.commit()

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="reader.lead_intent",
        target_type="lead",
        target_id=lead.id,
        details={
            "created": created,
            "telegram_user_id": payload.telegram_user_id,
            "intent_type": payload.intent_type,
            "post_id": str(payload.post_id) if payload.post_id else None,
        },
    )
    db.commit()
    return ReaderLeadIntentOut(lead_id=lead.id, created=created)

