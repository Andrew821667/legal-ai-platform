"""
Reader Bot Service Layer.

Functions for managing reader profiles, feedback, and interactions.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reader_models import UserProfile, LeadProfile, UserFeedback, UserInteraction, SavedArticle
from app.models.database import Publication, PostDraft


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
    await db.commit()
    await db.refresh(profile)
    return profile


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
) -> List[Publication]:
    """
    Get personalized article feed based on user's topics.
    Returns recent publications matching user interests.
    """
    profile = await get_user_profile(user_id, db)
    if not profile or not profile.topics:
        # No preferences - return most recent
        return await get_recent_publications(limit, db)

    # Get publications from last 7 days
    since = datetime.utcnow() - timedelta(days=7)

    # For now, simple filter by topics in draft content/title
    # TODO: Enhance with vector similarity search using Qdrant
    query = (
        select(Publication)
        .join(PostDraft, Publication.draft_id == PostDraft.id)
        .options(joinedload(Publication.draft))
        .where(Publication.published_at >= since)
        .order_by(desc(Publication.published_at))
        .limit(limit * 2)  # Get more, then filter
    )

    result = await db.execute(query)
    publications = result.scalars().all()

    # Filter by topics (simple keyword match)
    topic_keywords = {
        'gdpr': ['gdpr', 'персональн', 'пдн', 'защита данных', 'privacy'],
        'ai_law': ['искусственн', 'нейросет', 'машинн', 'ai', 'ml'],
        'crypto': ['крипто', 'блокчейн', 'биткоин', 'токен', 'nft'],
        'corporate': ['корпоративн', 'акционер', 'устав', 'ооо', 'ао'],
        'tax': ['налог', 'ндс', 'ндфл', 'налоговая', 'фнс'],
        'ip': ['авторск', 'патент', 'товарн', 'интеллектуальн']
    }

    filtered = []
    for pub in publications:
        if not pub.draft:
            continue

        content_lower = (pub.draft.title + ' ' + pub.draft.content).lower()

        # Check if any user topic matches
        for user_topic in profile.topics:
            keywords = topic_keywords.get(user_topic, [])
            if any(kw in content_lower for kw in keywords):
                filtered.append(pub)
                break  # Found match, add article

        if len(filtered) >= limit:
            break

    return filtered[:limit]


async def get_recent_publications(limit: int, db: AsyncSession) -> List[Publication]:
    """Get most recent publications (fallback for users without preferences)."""
    query = (
        select(Publication)
        .options(joinedload(Publication.draft))
        .order_by(desc(Publication.published_at))
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


# ==================== Search ====================

async def search_publications(
    query: str,
    user_id: Optional[int] = None,
    limit: int = 10,
    db: AsyncSession = None
) -> List[Publication]:
    """
    Full-text search publications by query.
    Optionally tracks search interaction.
    """
    # Search in title and content
    search_query = (
        select(Publication)
        .join(PostDraft, Publication.draft_id == PostDraft.id)
        .options(joinedload(Publication.draft))
        .where(
            or_(
                PostDraft.title.ilike(f'%{query}%'),
                PostDraft.content.ilike(f'%{query}%')
            )
        )
        .order_by(desc(Publication.published_at))
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

async def save_user_feedback(
    user_id: int,
    publication_id: int,
    is_useful: bool,
    feedback_type: Optional[str] = None,
    db: AsyncSession = None
):
    """Save user feedback (like/dislike) on article."""
    # Check if feedback exists
    existing = await db.execute(
        select(UserFeedback).where(
            and_(
                UserFeedback.user_id == user_id,
                UserFeedback.publication_id == publication_id
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
            publication_id=publication_id,
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

async def save_article(user_id: int, publication_id: int, db: AsyncSession):
    """Bookmark article for user."""
    # Check if already saved
    existing = await db.execute(
        select(SavedArticle).where(
            and_(
                SavedArticle.user_id == user_id,
                SavedArticle.publication_id == publication_id
            )
        )
    )

    if existing.scalar_one_or_none():
        return  # Already saved

    saved = SavedArticle(
        user_id=user_id,
        publication_id=publication_id
    )
    db.add(saved)

    # Track interaction
    interaction = UserInteraction(
        user_id=user_id,
        publication_id=publication_id,
        action='save'
    )
    db.add(interaction)

    await db.commit()


async def get_saved_articles(user_id: int, limit: int = 20, db: AsyncSession = None) -> List[Publication]:
    """Get user's saved articles."""
    query = (
        select(Publication)
        .join(SavedArticle, SavedArticle.publication_id == Publication.id)
        .options(joinedload(Publication.draft))
        .where(SavedArticle.user_id == user_id)
        .order_by(desc(SavedArticle.created_at))
        .limit(limit)
    )

    result = await db.execute(query)
    return result.scalars().all()


async def unsave_article(user_id: int, publication_id: int, db: AsyncSession):
    """Remove article from saved."""
    result = await db.execute(
        select(SavedArticle).where(
            and_(
                SavedArticle.user_id == user_id,
                SavedArticle.publication_id == publication_id
            )
        )
    )
    saved = result.scalar_one_or_none()

    if saved:
        await db.delete(saved)
        await db.commit()


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
