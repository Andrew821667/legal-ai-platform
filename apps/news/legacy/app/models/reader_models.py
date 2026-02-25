"""
SQLAlchemy models for Reader Bot.

Tables:
- UserProfile: Reader profiles with onboarding data
- LeadProfile: Extended profiles for qualified leads
- UserFeedback: Like/dislike feedback on articles
- UserInteraction: Engagement tracking
- SavedArticle: Bookmarked articles
"""

from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, String, Integer, Boolean, TIMESTAMP,
    Text, ARRAY, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from app.models.database import Base


class UserProfile(Base):
    """Reader bot user profile."""
    __tablename__ = 'user_profiles'

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)

    # Onboarding
    topics = Column(ARRAY(Text), nullable=True)  # ['gdpr', 'ai_law', 'crypto', ...]
    expertise_level = Column(String(50), nullable=True)  # 'student', 'lawyer', 'business'
    digest_frequency = Column(String(20), default='never')  # 'daily', 'twice_week', 'weekly', 'never'

    # Metadata
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    last_active = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Stats
    total_articles_viewed = Column(Integer, default=0)
    total_feedback_given = Column(Integer, default=0)

    # Relationships
    feedback = relationship("UserFeedback", back_populates="user", cascade="all, delete-orphan")
    interactions = relationship("UserInteraction", back_populates="user", cascade="all, delete-orphan")
    saved_articles = relationship("SavedArticle", back_populates="user", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_user_profiles_active', 'is_active'),
        Index('idx_user_profiles_digest', 'digest_frequency', postgresql_where=(digest_frequency != 'never')),
    )

    def __repr__(self):
        return f"<UserProfile(user_id={self.user_id}, username={self.username}, topics={self.topics})>"


class LeadProfile(Base):
    """Extended profile for qualified leads with contact information."""
    __tablename__ = 'lead_profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('user_profiles.user_id', ondelete='CASCADE'), nullable=False, unique=True)

    # Contact Information (Lead Magnet)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    company = Column(String(255), nullable=True)
    position = Column(String(255), nullable=True)

    # Lead Qualification
    lead_status = Column(String(50), default='interested')  # 'interested', 'qualified', 'converted', 'nurturing'
    expertise_level = Column(String(50), nullable=True)  # 'beginner', 'intermediate', 'expert', 'business_owner'
    business_focus = Column(String(100), nullable=True)  # 'law_firm', 'corporate', 'startup', 'consulting', 'other'

    # Lead Magnet Specific
    lead_magnet_completed = Column(Boolean, default=False)  # True if completed lead magnet flow
    questions_asked = Column(Integer, default=0)  # How many questions asked in lead magnet
    digest_requested = Column(Boolean, default=False)  # True if requested personalized digest

    # Lead Scoring
    lead_score = Column(Integer, default=0)  # 0-100 score based on engagement and qualification
    last_lead_activity = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Additional Business Info
    pain_points = Column(ARRAY(Text), nullable=True)  # What problems they want to solve
    budget_range = Column(String(50), nullable=True)  # 'under_100k', '100k_500k', '500k_1m', 'over_1m'
    timeline = Column(String(50), nullable=True)  # 'immediate', '3_months', '6_months', '1_year', 'researching'

    # CRM Integration
    crm_id = Column(String(100), nullable=True)  # External CRM system ID
    sales_notes = Column(Text, nullable=True)  # Notes for sales team

    # Metadata
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("UserProfile", backref="lead_profile")

    # Indexes
    __table_args__ = (
        Index('idx_lead_profiles_user_id', 'user_id'),
        Index('idx_lead_profiles_status', 'lead_status'),
        Index('idx_lead_profiles_expertise', 'expertise_level'),
        Index('idx_lead_profiles_score', 'lead_score'),
        Index('idx_lead_profiles_completed', 'lead_magnet_completed'),
        {'extend_existing': True}
    )

    def __repr__(self):
        return f"<LeadProfile(user_id={self.user_id}, lead_status={self.lead_status}, lead_score={self.lead_score})>"


class UserFeedback(Base):
    """User feedback (like/dislike) on articles."""
    __tablename__ = 'user_feedback'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('user_profiles.user_id', ondelete='CASCADE'), nullable=False)
    publication_id = Column(Integer, ForeignKey('publications.id', ondelete='CASCADE'), nullable=False)

    # Feedback
    is_useful = Column(Boolean, nullable=False)  # TRUE = 👍, FALSE = 👎
    feedback_type = Column(String(50), nullable=True)  # 'too_complex', 'not_relevant', etc.

    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserProfile", back_populates="feedback")
    publication = relationship("Publication")

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'publication_id', name='uq_user_feedback'),
        Index('idx_user_feedback_user', 'user_id'),
        Index('idx_user_feedback_publication', 'publication_id'),
        Index('idx_user_feedback_created', 'created_at'),
    )

    def __repr__(self):
        return f"<UserFeedback(user_id={self.user_id}, publication_id={self.publication_id}, is_useful={self.is_useful})>"


class UserInteraction(Base):
    """User engagement tracking (views, searches, shares)."""
    __tablename__ = 'user_interactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('user_profiles.user_id', ondelete='CASCADE'), nullable=False)
    publication_id = Column(Integer, ForeignKey('publications.id', ondelete='CASCADE'), nullable=True)

    # Interaction
    action = Column(String(50), nullable=False)  # 'view', 'save', 'share', 'search', 'digest_open'
    search_query = Column(Text, nullable=True)  # For 'search' actions
    source = Column(String(50), nullable=True)  # 'channel', 'channel_article', 'web', 'app', 'direct', 'search'

    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserProfile", back_populates="interactions")
    publication = relationship("Publication")

    # Indexes
    __table_args__ = (
        Index('idx_user_interactions_user', 'user_id'),
        Index('idx_user_interactions_publication', 'publication_id'),
        Index('idx_user_interactions_action', 'action'),
        Index('idx_user_interactions_created', 'created_at'),
        Index('idx_user_interactions_source', 'source'),
    )

    def __repr__(self):
        return f"<UserInteraction(user_id={self.user_id}, action={self.action}, publication_id={self.publication_id})>"


class SavedArticle(Base):
    """User bookmarked articles."""
    __tablename__ = 'saved_articles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('user_profiles.user_id', ondelete='CASCADE'), nullable=False)
    publication_id = Column(Integer, ForeignKey('publications.id', ondelete='CASCADE'), nullable=False)

    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("UserProfile", back_populates="saved_articles")
    publication = relationship("Publication")

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'publication_id', name='uq_saved_articles'),
        Index('idx_saved_articles_user', 'user_id'),
        Index('idx_saved_articles_publication', 'publication_id'),
    )

    def __repr__(self):
        return f"<SavedArticle(user_id={self.user_id}, publication_id={self.publication_id})>"
