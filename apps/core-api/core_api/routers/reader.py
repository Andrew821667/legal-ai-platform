from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.config import get_settings
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
    ReaderMiniAppEvent,
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
    ReaderMiniAppDeepLinkCreate,
    ReaderMiniAppDeepLinkOut,
    ReaderMiniAppEventCreate,
    ReaderMiniAppEventsSummaryOut,
    ReaderMiniAppEventOut,
    ReaderMiniAppProfileOut,
    ReaderMiniAppProfilePatch,
    ReaderMiniAppTopMetric,
    ReaderMiniAppTopUser,
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

_MINIAPP_SCREEN_TO_PATH: dict[str, str] = {
    "home": "/miniapp",
    "content": "/miniapp/content",
    "tools": "/miniapp/tools",
    "solutions": "/miniapp/solutions",
    "profile": "/miniapp/profile",
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


def _get_or_create_pref(db: Session, telegram_user_id: int) -> ReaderPreference:
    row = _pref_for_user(db, telegram_user_id)
    if row is not None:
        return row

    row = ReaderPreference(
        telegram_user_id=telegram_user_id,
        topics=[],
        digest_frequency="never",
        miniapp_interests=[],
    )
    db.add(row)
    db.flush()
    return row


def _normalize_audience(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"lawyer", "business", "mixed"}:
        return normalized
    return "mixed"


def _trim_optional_text(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized[:max_len]


def _miniapp_profile_out(row: ReaderPreference) -> ReaderMiniAppProfileOut:
    return ReaderMiniAppProfileOut(
        telegram_user_id=row.telegram_user_id,
        onboarding_done=bool(row.miniapp_onboarding_done),
        audience=_normalize_audience(row.miniapp_audience),
        interests=_normalize_topics((row.miniapp_interests if isinstance(row.miniapp_interests, list) else []) or []),
        goal=row.miniapp_goal,
        last_action=row.miniapp_last_action,
        topics=_normalize_topics((row.topics if isinstance(row.topics, list) else []) or []),
        digest_frequency=str(row.digest_frequency or "never"),
        expertise_level=row.expertise_level,
        updated_at=row.updated_at,
    )


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


@router.get("/miniapp/profile", response_model=ReaderMiniAppProfileOut)
def get_reader_miniapp_profile(
    telegram_user_id: int = Query(ge=1),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> ReaderMiniAppProfileOut:
    _ = identity
    row = _get_or_create_pref(db, telegram_user_id)
    db.commit()
    db.refresh(row)
    return _miniapp_profile_out(row)


@router.patch("/miniapp/profile", response_model=ReaderMiniAppProfileOut)
def patch_reader_miniapp_profile(
    payload: ReaderMiniAppProfilePatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> ReaderMiniAppProfileOut:
    row = _get_or_create_pref(db, payload.telegram_user_id)

    if payload.onboarding_done is not None:
        row.miniapp_onboarding_done = bool(payload.onboarding_done)
    if payload.audience is not None:
        row.miniapp_audience = _normalize_audience(payload.audience)
    if payload.interests is not None:
        normalized_interests = _normalize_topics(payload.interests)
        row.miniapp_interests = normalized_interests
        if payload.sync_reader_topics:
            row.topics = normalized_interests
    if payload.goal is not None:
        row.miniapp_goal = _trim_optional_text(payload.goal, max_len=4000)
    if payload.last_action is not None:
        row.miniapp_last_action = _trim_optional_text(payload.last_action, max_len=255)
    if payload.digest_frequency is not None:
        row.digest_frequency = _trim_optional_text(payload.digest_frequency, max_len=50) or "never"
    if payload.expertise_level is not None:
        row.expertise_level = _trim_optional_text(payload.expertise_level, max_len=50)

    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="reader.miniapp.profile.patch",
        target_type="reader_preference",
        target_id=row.id,
        details={"telegram_user_id": row.telegram_user_id},
    )
    db.commit()
    return _miniapp_profile_out(row)


@router.post("/miniapp/event", response_model=ReaderMiniAppEventOut)
def create_reader_miniapp_event(
    payload: ReaderMiniAppEventCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> ReaderMiniAppEvent:
    row = ReaderMiniAppEvent(
        telegram_user_id=payload.telegram_user_id,
        event_type=payload.event_type.strip()[:100],
        source=_trim_optional_text(payload.source, max_len=50) or "miniapp",
        screen=_trim_optional_text(payload.screen, max_len=120),
        action=_trim_optional_text(payload.action, max_len=120),
        payload=payload.payload,
    )
    db.add(row)

    if payload.update_last_action and payload.action:
        pref = _get_or_create_pref(db, payload.telegram_user_id)
        pref.miniapp_last_action = _trim_optional_text(payload.action, max_len=255)
        pref.updated_at = datetime.now(timezone.utc)
        db.add(pref)

    db.commit()
    db.refresh(row)

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="reader.miniapp.event.create",
        target_type="reader_miniapp_event",
        target_id=row.id,
        details={
            "telegram_user_id": payload.telegram_user_id,
            "event_type": payload.event_type,
            "source": payload.source or "miniapp",
        },
    )
    db.commit()
    return row


@router.get("/miniapp/events", response_model=list[ReaderMiniAppEventOut])
def list_reader_miniapp_events(
    telegram_user_id: int = Query(ge=1),
    limit: int = Query(default=30, ge=1, le=200),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> list[ReaderMiniAppEvent]:
    _ = identity
    return list(
        db.execute(
            select(ReaderMiniAppEvent)
            .where(ReaderMiniAppEvent.telegram_user_id == telegram_user_id)
            .order_by(ReaderMiniAppEvent.created_at.desc())
            .limit(limit)
        ).scalars().all()
    )


@router.get("/miniapp/events/summary", response_model=ReaderMiniAppEventsSummaryOut)
def summarize_reader_miniapp_events(
    hours: int = Query(default=24, ge=1, le=168),
    limit_users: int = Query(default=10, ge=1, le=50),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> ReaderMiniAppEventsSummaryOut:
    _ = identity
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    base_where = ReaderMiniAppEvent.created_at >= since

    total_events = int(
        db.execute(select(func.count()).select_from(ReaderMiniAppEvent).where(base_where)).scalar() or 0
    )
    unique_users = int(
        db.execute(
            select(func.count(func.distinct(ReaderMiniAppEvent.telegram_user_id))).where(base_where)
        ).scalar()
        or 0
    )

    def _top_metrics(column, *, limit: int = 8) -> list[ReaderMiniAppTopMetric]:
        rows = db.execute(
            select(column.label("label"), func.count().label("count"))
            .where(base_where)
            .where(column.is_not(None))
            .group_by(column)
            .order_by(func.count().desc(), column.asc())
            .limit(limit)
        ).all()
        return [
            ReaderMiniAppTopMetric(label=str(label), count=int(count or 0))
            for label, count in rows
            if str(label or "").strip()
        ]

    top_users_rows = db.execute(
        select(ReaderMiniAppEvent.telegram_user_id, func.count().label("count"))
        .where(base_where)
        .group_by(ReaderMiniAppEvent.telegram_user_id)
        .order_by(func.count().desc(), ReaderMiniAppEvent.telegram_user_id.asc())
        .limit(limit_users)
    ).all()
    top_users = [
        ReaderMiniAppTopUser(telegram_user_id=int(user_id), count=int(count or 0))
        for user_id, count in top_users_rows
    ]

    recent_events = list(
        db.execute(
            select(ReaderMiniAppEvent)
            .where(base_where)
            .order_by(ReaderMiniAppEvent.created_at.desc())
            .limit(20)
        ).scalars().all()
    )

    return ReaderMiniAppEventsSummaryOut(
        hours=hours,
        total_events=total_events,
        unique_users=unique_users,
        top_sources=_top_metrics(ReaderMiniAppEvent.source),
        top_event_types=_top_metrics(ReaderMiniAppEvent.event_type),
        top_screens=_top_metrics(ReaderMiniAppEvent.screen),
        top_actions=_top_metrics(ReaderMiniAppEvent.action),
        top_users=top_users,
        recent_events=recent_events,
    )


@router.post("/miniapp/deeplink", response_model=ReaderMiniAppDeepLinkOut)
def build_reader_miniapp_deeplink(
    payload: ReaderMiniAppDeepLinkCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.news, Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> ReaderMiniAppDeepLinkOut:
    screen = _trim_optional_text(payload.screen, max_len=32) or "home"
    path = _MINIAPP_SCREEN_TO_PATH.get(screen, _MINIAPP_SCREEN_TO_PATH["home"])

    query: dict[str, str] = {
        "tg": str(payload.telegram_user_id),
        "src": _trim_optional_text(payload.source, max_len=64) or "reader_bot",
        "screen": screen,
    }
    action = _trim_optional_text(payload.action, max_len=64)
    if action:
        query["act"] = action
    if payload.post_id is not None:
        query["post_id"] = str(payload.post_id)

    query_string = urlencode(query)
    base_url = (get_settings().miniapp_public_base_url or "").strip().rstrip("/")
    if not base_url.lower().startswith("https://"):
        base_url = "https://legalaipro.ru"
    url = f"{base_url}{path}" if not query_string else f"{base_url}{path}?{query_string}"

    event = ReaderMiniAppEvent(
        telegram_user_id=payload.telegram_user_id,
        event_type="deeplink_issued",
        source=query["src"],
        screen=screen,
        action=action,
        payload={"post_id": str(payload.post_id) if payload.post_id else None, **payload.payload},
    )
    db.add(event)
    db.commit()

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="reader.miniapp.deeplink",
        target_type="reader_miniapp_event",
        target_id=event.id,
        details={"telegram_user_id": payload.telegram_user_id, "screen": screen, "path": path},
    )
    db.commit()

    return ReaderMiniAppDeepLinkOut(path=path, url=url, query=query)


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
