"""
Reader Bot Service Layer.

Functions for managing reader profiles, feedback, and interactions.
"""

import logging
from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional, List, Dict
from sqlalchemy import select, func, and_, or_, desc, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.reader_models import UserProfile, LeadProfile, UserFeedback, UserInteraction, SavedArticle
from app.models.reader_publications import ReaderPublication
from app.services.core_reader_bridge import (
    fetch_reader_feed,
    fetch_reader_saved,
    push_reader_preferences,
    push_reader_save_state,
)

logger = logging.getLogger(__name__)

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "gdpr": ["gdpr", "персональн", "пдн", "защита данных", "privacy"],
    "ai_law": ["искусственн", "нейросет", "машинн", "ai", "ml"],
    "crypto": ["крипто", "блокчейн", "биткоин", "токен", "nft"],
    "corporate": ["корпоративн", "акционер", "устав", "ооо", "ао"],
    "tax": ["налог", "ндс", "ндфл", "налоговая", "фнс"],
    "ip": ["авторск", "патент", "товарн", "интеллектуальн"],
}


# ==================== User Profile Management ====================

async def get_user_profile(user_id: int, db: AsyncSession) -> Optional[UserProfile]:
    """Get user profile by user_id."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_user_profile(
    user_id: int,
    username: Optional[str],
    full_name: Optional[str],
    db: AsyncSession
) -> UserProfile:
    """Create new user profile."""
    profile = UserProfile(
        user_id=user_id,
        username=username,
        full_name=full_name,
        topics=[],  # Empty, will be filled during onboarding
        expertise_level=None,
        digest_frequency='never',
        is_active=True
    )
    db.add(profile)
    try:
        await db.commit()
        await db.refresh(profile)
        return profile
    except IntegrityError:
        # Idempotent create: profile may already exist due duplicate updates/retries.
        await db.rollback()
        existing = await get_user_profile(user_id, db)
        if existing:
            return existing
        raise


async def update_user_profile(
    user_id: int,
    topics: Optional[List[str]] = None,
    expertise_level: Optional[str] = None,
    digest_frequency: Optional[str] = None,
    db: AsyncSession = None
) -> Optional[UserProfile]:
    """Update user profile."""
    profile = await get_user_profile(user_id, db)
    if not profile:
        return None

    if topics is not None:
        profile.topics = topics
    if expertise_level is not None:
        profile.expertise_level = expertise_level
    if digest_frequency is not None:
        profile.digest_frequency = digest_frequency

    profile.last_active = datetime.utcnow()

    await db.commit()
    await db.refresh(profile)
    if topics is not None or digest_frequency is not None or expertise_level is not None:
        await push_reader_preferences(
            user_id=user_id,
            topics=list(profile.topics or []),
            digest_frequency=profile.digest_frequency,
            expertise_level=profile.expertise_level,
        )
    return profile


async def update_last_active(user_id: int, db: AsyncSession):
    """Update user's last_active timestamp."""
    profile = await get_user_profile(user_id, db)
    if profile:
        profile.last_active = datetime.utcnow()
        await db.commit()


# ==================== Lead Profile Management ====================

async def get_lead_profile(user_id: int, db: AsyncSession) -> Optional[LeadProfile]:
    """Get lead profile by user_id."""
    result = await db.execute(
        select(LeadProfile).where(LeadProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_lead_profile(
    user_id: int,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company: Optional[str] = None,
    position: Optional[str] = None,
    db: AsyncSession = None
) -> LeadProfile:
    """Create new lead profile."""
    lead_profile = LeadProfile(
        user_id=user_id,
        email=email,
        phone=phone,
        company=company,
        position=position,
        lead_status='interested',
        lead_score=0,
        lead_magnet_completed=False
    )
    db.add(lead_profile)
    await db.commit()
    await db.refresh(lead_profile)
    return lead_profile


async def update_lead_profile(
    user_id: int,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company: Optional[str] = None,
    position: Optional[str] = None,
    lead_status: Optional[str] = None,
    expertise_level: Optional[str] = None,
    business_focus: Optional[str] = None,
    lead_score: Optional[int] = None,
    pain_points: Optional[List[str]] = None,
    budget_range: Optional[str] = None,
    timeline: Optional[str] = None,
    lead_magnet_completed: Optional[bool] = None,
    digest_requested: Optional[bool] = None,
    db: AsyncSession = None
) -> Optional[LeadProfile]:
    """Update lead profile."""
    lead_profile = await get_lead_profile(user_id, db)
    if not lead_profile:
        return None

    if email is not None:
        lead_profile.email = email
    if phone is not None:
        lead_profile.phone = phone
    if company is not None:
        lead_profile.company = company
    if position is not None:
        lead_profile.position = position
    if lead_status is not None:
        lead_profile.lead_status = lead_status
    if expertise_level is not None:
        lead_profile.expertise_level = expertise_level
    if business_focus is not None:
        lead_profile.business_focus = business_focus
    if lead_score is not None:
        lead_profile.lead_score = lead_score
    if pain_points is not None:
        lead_profile.pain_points = pain_points
    if budget_range is not None:
        lead_profile.budget_range = budget_range
    if timeline is not None:
        lead_profile.timeline = timeline
    if lead_magnet_completed is not None:
        lead_profile.lead_magnet_completed = lead_magnet_completed
    if digest_requested is not None:
        lead_profile.digest_requested = digest_requested

    lead_profile.last_lead_activity = datetime.utcnow()

    await db.commit()
    await db.refresh(lead_profile)
    return lead_profile


async def increment_questions_asked(user_id: int, db: AsyncSession):
    """Increment counter of questions asked in lead magnet."""
    lead_profile = await get_lead_profile(user_id, db)
    if lead_profile:
        lead_profile.questions_asked += 1
        lead_profile.last_lead_activity = datetime.utcnow()
        await db.commit()


async def calculate_lead_score(user_id: int, db: AsyncSession) -> int:
    """
    Calculate lead score based on engagement and qualification.
    Returns score 0-100.
    """
    profile = await get_user_profile(user_id, db)
    lead_profile = await get_lead_profile(user_id, db)

    if not profile or not lead_profile:
        return 0

    score = 0

    # Base score for completing onboarding
    if profile.topics:
        score += 20

    # Score for completing lead magnet
    if lead_profile.lead_magnet_completed:
        score += 30

    # Score for contact information completeness
    contact_fields = [lead_profile.email, lead_profile.phone, lead_profile.company]
    contact_score = sum(1 for field in contact_fields if field) * 5
    score += contact_score

    # Score for business information
    business_fields = [lead_profile.position, lead_profile.business_focus, lead_profile.expertise_level]
    business_score = sum(1 for field in business_fields if field) * 5
    score += business_score

    # Engagement score based on interactions
    interactions_count = await get_user_interactions_count(user_id, db)
    engagement_score = min(interactions_count * 2, 20)  # Max 20 points
    score += engagement_score

    return min(score, 100)  # Cap at 100


async def get_user_interactions_count(user_id: int, db: AsyncSession) -> int:
    """Get total user interactions count."""
    result = await db.execute(
        select(func.count(UserInteraction.id)).where(UserInteraction.user_id == user_id)
    )
    return result.scalar() or 0


async def get_leads_by_status(lead_status: str, db: AsyncSession) -> List[LeadProfile]:
    """Get leads filtered by status."""
    result = await db.execute(
        select(LeadProfile)
        .where(LeadProfile.lead_status == lead_status)
        .order_by(desc(LeadProfile.created_at))
    )
    return result.scalars().all()


async def get_top_leads(limit: int = 10, db: AsyncSession = None) -> List[LeadProfile]:
    """Get top leads by score."""
    result = await db.execute(
        select(LeadProfile)
        .where(LeadProfile.lead_score > 0)
        .order_by(desc(LeadProfile.lead_score))
        .limit(limit)
    )
    return result.scalars().all()


# ==================== Personalized Feed ====================

async def get_personalized_feed(
    user_id: int,
    limit: int = 5,
    db: AsyncSession = None
) -> List[ReaderPublication]:
    """
    Get personalized article feed based on user's topics.
    Returns recent publications matching user interests.
    """
    core_feed = await fetch_reader_feed(user_id=user_id, limit=limit, days=14)
    if core_feed is not None:
        if not core_feed:
            return []
        core_ids = [str(item.get("id", "")).strip() for item in core_feed if str(item.get("id", "")).strip()]
        publications = await _ordered_publications_by_ids(core_ids, db=db)
        if publications:
            return publications[:limit]

    profile = await get_user_profile(user_id, db)
    if not profile or not profile.topics:
        # No preferences - return most recent
        return await get_recent_publications(limit, db)

    # Get publications from last 7 days
    since = datetime.utcnow() - timedelta(days=7)

    # For now, simple filter by topics in draft content/title
    # TODO: Enhance with vector similarity search using Qdrant
    query = (
        select(ReaderPublication)
        .where(cast(ReaderPublication.status, String) == "posted")
        .where(ReaderPublication.publish_at >= since)
        .order_by(desc(ReaderPublication.publish_at))
        .limit(limit * 2)
    )

    result = await db.execute(query)
    publications = result.scalars().all()

    filtered = []
    for pub in publications:
        content_lower = ((pub.title or "") + " " + (pub.text or "")).lower()

        # Check if any user topic matches
        for user_topic in profile.topics:
            keywords = TOPIC_KEYWORDS.get(user_topic, [])
            if any(kw in content_lower for kw in keywords):
                filtered.append(pub)
                break  # Found match, add article

        if len(filtered) >= limit:
            break

    return filtered[:limit]


async def get_recent_publications(limit: int, db: AsyncSession) -> List[ReaderPublication]:
    """Get most recent publications (fallback for users without preferences)."""
    query = (
        select(ReaderPublication)
        .where(cast(ReaderPublication.status, String) == "posted")
        .order_by(desc(ReaderPublication.publish_at))
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


async def get_weekly_digest_candidates(
    user_id: int,
    limit: int = 8,
    days: int = 7,
    db: AsyncSession = None,
) -> List[ReaderPublication]:
    """
    Select a compact list of weekly digest candidates.
    Priority: user topics -> recency -> uniqueness by title.
    """
    profile = await get_user_profile(user_id, db)
    user_topics = list(profile.topics or []) if profile else []

    since = datetime.utcnow() - timedelta(days=max(days, 1))
    query = (
        select(ReaderPublication)
        .where(cast(ReaderPublication.status, String) == "posted")
        .where(ReaderPublication.publish_at >= since)
        .order_by(desc(ReaderPublication.publish_at))
        .limit(max(limit * 8, 40))
    )
    result = await db.execute(query)
    publications = result.scalars().all()
    if not publications:
        return []

    selected: List[ReaderPublication] = []
    seen_titles: set[str] = set()

    def _title_key(pub: ReaderPublication) -> str:
        return " ".join((pub.title or "").lower().split())[:220]

    def _matches_topics(pub: ReaderPublication) -> bool:
        if not user_topics:
            return True
        content_lower = ((pub.title or "") + " " + (pub.text or "")).lower()
        for topic in user_topics:
            for kw in TOPIC_KEYWORDS.get(topic, []):
                if kw in content_lower:
                    return True
        return False

    # First pass: strictly by user topics
    for pub in publications:
        key = _title_key(pub)
        if not key or key in seen_titles:
            continue
        if _matches_topics(pub):
            selected.append(pub)
            seen_titles.add(key)
        if len(selected) >= limit:
            return selected

    # Second pass: fill with generally relevant recent posts
    for pub in publications:
        key = _title_key(pub)
        if not key or key in seen_titles:
            continue
        selected.append(pub)
        seen_titles.add(key)
        if len(selected) >= limit:
            break

    return selected


async def get_publication_by_id(publication_id: str | UUID, db: AsyncSession) -> Optional[ReaderPublication]:
    """Get a posted publication by UUID."""
    try:
        publication_uuid = publication_id if isinstance(publication_id, UUID) else UUID(str(publication_id))
    except ValueError:
        return None

    result = await db.execute(
        select(ReaderPublication).where(
            and_(
                ReaderPublication.id == publication_uuid,
                cast(ReaderPublication.status, String) == "posted",
            )
        )
    )
    return result.scalar_one_or_none()


async def _ordered_publications_by_ids(ids: list[str], db: AsyncSession) -> List[ReaderPublication]:
    """Load posted publications by IDs and preserve requested order."""
    if not ids:
        return []

    parsed_ids: list[UUID] = []
    for raw_id in ids:
        try:
            parsed_ids.append(UUID(str(raw_id)))
        except ValueError:
            continue
    if not parsed_ids:
        return []

    result = await db.execute(
        select(ReaderPublication).where(
            and_(
                ReaderPublication.id.in_(parsed_ids),
                cast(ReaderPublication.status, String) == "posted",
            )
        )
    )
    rows = result.scalars().all()
    by_id = {str(row.id): row for row in rows}
    ordered: list[ReaderPublication] = []
    for item_id in parsed_ids:
        row = by_id.get(str(item_id))
        if row is not None:
            ordered.append(row)
    return ordered


# ==================== Search ====================

async def search_publications(
    query: str,
    user_id: Optional[int] = None,
    limit: int = 10,
    db: AsyncSession = None
) -> List[ReaderPublication]:
    """
    Full-text search publications by query.
    Optionally tracks search interaction.
    """
    # Search in title and content
    search_query = (
        select(ReaderPublication)
        .where(
            or_(
                ReaderPublication.title.ilike(f"%{query}%"),
                ReaderPublication.text.ilike(f"%{query}%"),
            )
        )
        .where(cast(ReaderPublication.status, String) == "posted")
        .order_by(desc(ReaderPublication.publish_at))
        .limit(limit)
    )

    result = await db.execute(search_query)
    publications = result.scalars().all()

    # Track search interaction
    if user_id:
        interaction = UserInteraction(
            user_id=user_id,
            action='search',
            search_query=query
        )
        db.add(interaction)
        await db.commit()

    return publications


# ==================== Feedback ====================

def _parse_publication_id(publication_id: str | UUID) -> UUID:
    """Normalize callback/public API publication IDs to UUID."""
    if isinstance(publication_id, UUID):
        return publication_id
    return UUID(str(publication_id))


def _publication_match(column, publication_uuid: UUID):
    """
    Compatibility comparison by string representation.
    Works for uuid/bigint legacy columns without operator mismatch errors.
    """
    return cast(column, String) == str(publication_uuid)


async def save_user_feedback(
    user_id: int,
    publication_id: str | UUID,
    is_useful: bool,
    feedback_type: Optional[str] = None,
    db: AsyncSession = None
):
    """Save user feedback (like/dislike) on article."""
    publication_uuid = _parse_publication_id(publication_id)

    # Check if feedback exists
    existing = await db.execute(
        select(UserFeedback).where(
            and_(
                UserFeedback.user_id == user_id,
                _publication_match(UserFeedback.publication_id, publication_uuid),
            )
        )
    )
    feedback = existing.scalar_one_or_none()

    if feedback:
        # Update existing
        feedback.is_useful = is_useful
        feedback.feedback_type = feedback_type
    else:
        # Create new
        feedback = UserFeedback(
            user_id=user_id,
            publication_id=publication_uuid,
            is_useful=is_useful,
            feedback_type=feedback_type
        )
        db.add(feedback)

        # Increment user stats
        profile = await get_user_profile(user_id, db)
        if profile:
            profile.total_feedback_given += 1

    await db.commit()


# ==================== Saved Articles ====================

async def save_article(user_id: int, publication_id: str | UUID, db: AsyncSession):
    """Bookmark article for user."""
    publication_uuid = _parse_publication_id(publication_id)

    # Check if already saved
    existing = await db.execute(
        select(SavedArticle).where(
            and_(
                SavedArticle.user_id == user_id,
                _publication_match(SavedArticle.publication_id, publication_uuid),
            )
        )
    )

    if existing.scalar_one_or_none():
        await push_reader_save_state(
            user_id=user_id,
            publication_id=str(publication_uuid),
            saved=True,
        )
        return  # Already saved

    saved = SavedArticle(
        user_id=user_id,
        publication_id=publication_uuid
    )
    db.add(saved)

    # Track interaction
    interaction = UserInteraction(
        user_id=user_id,
        publication_id=publication_uuid,
        action='save'
    )
    db.add(interaction)

    await db.commit()
    await push_reader_save_state(
        user_id=user_id,
        publication_id=str(publication_uuid),
        saved=True,
    )


async def get_saved_articles(user_id: int, limit: int = 20, db: AsyncSession = None) -> List[ReaderPublication]:
    """Get user's saved articles."""
    core_saved = await fetch_reader_saved(user_id=user_id, limit=limit)
    if core_saved is not None:
        ids = [str(item.get("id", "")).strip() for item in core_saved if str(item.get("id", "")).strip()]
        return await _ordered_publications_by_ids(ids, db=db)

    query = (
        select(ReaderPublication)
        .join(SavedArticle, cast(SavedArticle.publication_id, String) == cast(ReaderPublication.id, String))
        .where(cast(ReaderPublication.status, String) == "posted")
        .where(SavedArticle.user_id == user_id)
        .order_by(desc(SavedArticle.created_at))
        .limit(limit)
    )
    try:
        result = await db.execute(query)
        return result.scalars().all()
    except Exception:
        logger.exception("get_saved_articles_failed", extra={"user_id": user_id})
        return []


async def unsave_article(user_id: int, publication_id: str | UUID, db: AsyncSession):
    """Remove article from saved."""
    publication_uuid = _parse_publication_id(publication_id)

    result = await db.execute(
        select(SavedArticle).where(
            and_(
                SavedArticle.user_id == user_id,
                _publication_match(SavedArticle.publication_id, publication_uuid),
            )
        )
    )
    saved = result.scalar_one_or_none()

    if saved:
        await db.delete(saved)
        await db.commit()
    await push_reader_save_state(
        user_id=user_id,
        publication_id=str(publication_uuid),
        saved=False,
    )


# ==================== Analytics ====================

async def get_user_stats(user_id: int, db: AsyncSession) -> Dict:
    """Get user engagement statistics."""
    profile = await get_user_profile(user_id, db)
    if not profile:
        return {}

    # Count saved articles
    saved_count = await db.execute(
        select(func.count(SavedArticle.id)).where(SavedArticle.user_id == user_id)
    )

    # Count positive feedback
    positive_feedback = await db.execute(
        select(func.count(UserFeedback.id)).where(
            and_(
                UserFeedback.user_id == user_id,
                UserFeedback.is_useful == True
            )
        )
    )

    return {
        'articles_viewed': profile.total_articles_viewed,
        'feedback_given': profile.total_feedback_given,
        'articles_saved': saved_count.scalar() or 0,
        'positive_feedback': positive_feedback.scalar() or 0,
        'member_since': profile.created_at,
        'last_active': profile.last_active
    }
