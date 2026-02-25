"""
Database models and connection management using SQLAlchemy.
"""

from datetime import datetime
from typing import AsyncGenerator, Optional, List
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, TIMESTAMP,
    BigInteger, ForeignKey, CheckConstraint, Index, ARRAY, text, Date, Numeric
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func

from app.config import settings


# ====================
# Base Model
# ====================

class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# ====================
# Database Models
# ====================

class RawArticle(Base):
    """Сырые статьи из RSS и других источников."""

    __tablename__ = "raw_articles"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text)
    source_name = Column(String(100), nullable=False, index=True)
    published_at = Column(TIMESTAMP)
    fetched_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    status = Column(String(20), default='new', index=True)
    relevance_score = Column(Float)
    scored_at = Column(TIMESTAMP, index=True)  # Время последней оценки AI

    # Relationships
    drafts = relationship("PostDraft", back_populates="article", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'filtered', 'processed', 'rejected')",
            name='chk_status'
        ),
    )


class LegalKnowledge(Base):
    """База знаний юридических документов для RAG."""

    __tablename__ = "legal_knowledge"

    id = Column(Integer, primary_key=True, index=True)
    doc_name = Column(String(200), nullable=False, index=True)
    article_number = Column(String(50))
    text_chunk = Column(Text, nullable=False)
    keywords = Column(ARRAY(Text))
    # ts_vector handled by PostgreSQL generated column


class PostDraft(Base):
    """Драфты постов для модерации."""

    __tablename__ = "post_drafts"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("raw_articles.id", ondelete="CASCADE"))
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    legal_context = Column(Text)
    image_path = Column(Text)
    audio_path = Column(Text)
    confidence_score = Column(Float)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    reviewed_at = Column(TIMESTAMP)
    reviewed_by = Column(Integer)
    status = Column(String(20), default='pending_review', index=True)
    rejection_reason = Column(Text)

    # Relationships
    article = relationship("RawArticle", back_populates="drafts")
    publications = relationship("Publication", back_populates="draft", cascade="all, delete-orphan")
    media_files = relationship("MediaFile", back_populates="draft", cascade="all, delete-orphan")
    feedback = relationship("FeedbackLabel", back_populates="draft", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_review', 'approved', 'rejected', 'edited')",
            name='chk_draft_status'
        ),
    )


class Publication(Base):
    """Опубликованные посты в Telegram канале."""

    __tablename__ = "publications"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("post_drafts.id", ondelete="CASCADE"), index=True)
    message_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False)
    published_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    views = Column(Integer, default=0)
    reactions = Column(JSONB, default={})
    forwards = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)

    # Relationships
    draft = relationship("PostDraft", back_populates="publications")
    analytics = relationship("PostAnalytics", back_populates="publication", cascade="all, delete-orphan")


class PostAnalytics(Base):
    """Аналитика по опубликованным постам."""

    __tablename__ = "post_analytics"

    id = Column(Integer, primary_key=True, index=True)
    publication_id = Column(Integer, ForeignKey("publications.id", ondelete="CASCADE"), index=True)
    views = Column(Integer, default=0)
    reactions = Column(JSONB, default={})
    utm_clicks = Column(Integer, default=0)
    avg_read_time = Column(Integer)  # seconds
    collected_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)

    # Relationships
    publication = relationship("Publication", back_populates="analytics")


class FeedbackLabel(Base):
    """Обучающие данные для ML (feedback loop)."""

    __tablename__ = "feedback_labels"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("post_drafts.id", ondelete="CASCADE"), index=True)
    admin_action = Column(String(20), nullable=False)
    rejection_reason = Column(Text)
    performance_score = Column(Float)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)

    # Relationships
    draft = relationship("PostDraft", back_populates="feedback")

    __table_args__ = (
        CheckConstraint(
            "admin_action IN ('published', 'rejected', 'edited')",
            name='chk_admin_action'
        ),
    )


class Source(Base):
    """Управление источниками новостей."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    url = Column(Text, nullable=False)
    type = Column(String(20), nullable=False)
    enabled = Column(Boolean, default=True, index=True)
    last_fetch = Column(TIMESTAMP)
    fetch_errors = Column(Integer, default=0)
    quality_score = Column(Float, default=0.5, index=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ('rss', 'web', 'telegram')",
            name='chk_source_type'
        ),
    )


class SystemLog(Base):
    """Системные логи приложения."""

    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(10), nullable=False, index=True)
    message = Column(Text, nullable=False)
    context = Column(JSONB)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)

    __table_args__ = (
        CheckConstraint(
            "level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')",
            name='chk_log_level'
        ),
    )


class MediaFile(Base):
    """Медиа файлы (обложки, аудио)."""

    __tablename__ = "media_files"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("post_drafts.id", ondelete="CASCADE"), index=True)
    file_type = Column(String(10), nullable=False, index=True)
    file_path = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    draft = relationship("PostDraft", back_populates="media_files")

    __table_args__ = (
        CheckConstraint(
            "file_type IN ('image', 'audio')",
            name='chk_file_type'
        ),
    )


class APIUsage(Base):
    """Статистика использования API (OpenAI, Perplexity) для отслеживания стоимости."""

    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)  # openai, perplexity
    model = Column(String(100), nullable=False, index=True)  # gpt-4o-mini, sonar, etc
    operation = Column(String(100), index=True)  # ranking, draft_generation, editing, etc

    # Токены
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # Стоимость в USD
    cost_usd = Column(Numeric(10, 6), default=0.0)  # До 6 знаков после запятой

    # Метаданные
    article_id = Column(Integer, ForeignKey("raw_articles.id", ondelete="SET NULL"), nullable=True, index=True)
    draft_id = Column(Integer, ForeignKey("post_drafts.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    date = Column(Date, default=datetime.utcnow, index=True)  # Для группировки по дням/месяцам


class MonthlyAPIStats(Base):
    """Агрегированная статистика API за месяц для быстрого доступа."""

    __tablename__ = "monthly_api_stats"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)  # 1-12
    provider = Column(String(50), nullable=False, index=True)

    total_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Numeric(10, 6), default=0.0)

    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_monthly_stats_unique', 'year', 'month', 'provider', unique=True),
    )


class SystemSettings(Base):
    """Системные настройки приложения (управляются через UI)."""

    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text)  # JSON or string value
    type = Column(String(20), nullable=False)  # bool, string, int, float, json
    category = Column(String(50), nullable=False, index=True)  # sources, llm, publishing, media, etc
    description = Column(Text)

    # Metadata
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "type IN ('bool', 'string', 'int', 'float', 'json')",
            name='valid_setting_type'
        ),
    )


class PersonalPost(Base):
    """Личные посты пользователя (дневник работы с AI)."""

    __tablename__ = "personal_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)  # Telegram user ID

    # Контент
    title = Column(String(500))  # Опциональный заголовок
    content = Column(Text, nullable=False)  # Основной текст поста
    raw_input = Column(Text)  # Оригинальный ввод пользователя (до AI обработки)

    # Метаданные создания
    creation_method = Column(String(50), nullable=False)  # manual, ai_assisted, voice
    ai_model_used = Column(String(100))  # Какая модель использовалась для генерации
    iterations_count = Column(Integer, default=1)  # Сколько итераций потребовалось

    # Категоризация и теги (автоматические и ручные)
    category = Column(String(100))  # Категория (AI определяет)
    tags = Column(ARRAY(String))  # Теги для поиска
    sentiment = Column(String(50))  # positive, neutral, negative (AI анализ)

    # Векторное представление для RAG
    embedding_vector = Column(ARRAY(Float))  # OpenAI embeddings (1536 dimensions)
    embedding_model = Column(String(100))  # text-embedding-3-small или другая

    # Связи с публикациями
    related_article_ids = Column(ARRAY(Integer))  # ID связанных статей
    similarity_scores = Column(ARRAY(Float))  # Similarity scores для каждой связанной статьи

    # Публикация
    published = Column(Boolean, default=False)
    published_at = Column(TIMESTAMP)
    telegram_message_id = Column(BigInteger)  # ID сообщения в канале

    # Статистика (если опубликовано)
    views_count = Column(Integer, default=0)
    reactions_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_personal_posts_user_created', 'user_id', 'created_at'),
        Index('idx_personal_posts_published', 'published', 'published_at'),
    )


class PostComment(Base):
    """Комментарии к личным постам (рефлексия и развитие идей)."""

    __tablename__ = "post_comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, nullable=False, index=True)  # FK to personal_posts.id
    user_id = Column(BigInteger, nullable=False)  # Telegram user ID

    # Контент комментария
    content = Column(Text, nullable=False)

    # Метаданные
    comment_type = Column(String(50), default='reflection')  # reflection, idea, question, update

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_post_comments_post', 'post_id', 'created_at'),
    )


class LeadProfile(Base):
    """Расширенные профили лидов с контактной информацией и квалификацией."""

    __tablename__ = "lead_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False, unique=True, index=True)

    # Contact Information (Lead Magnet)
    email = Column(String(255))
    phone = Column(String(50))
    company = Column(String(255))
    position = Column(String(255))

    # Lead Qualification
    lead_status = Column(String(50), default='interested')  # 'interested', 'qualified', 'converted', 'nurturing'
    expertise_level = Column(String(50))                    # 'beginner', 'intermediate', 'expert', 'business_owner'
    business_focus = Column(String(100))                    # 'law_firm', 'corporate', 'startup', 'consulting', 'other'

    # Lead Magnet Specific
    lead_magnet_completed = Column(Boolean, default=False)   # True if completed lead magnet flow
    questions_asked = Column(Integer, default=0)             # How many questions asked in lead magnet
    digest_requested = Column(Boolean, default=False)        # True if requested personalized digest

    # Lead Scoring
    lead_score = Column(Integer, default=0)                  # 0-100 score based on engagement and qualification
    last_lead_activity = Column(TIMESTAMP, default=datetime.utcnow)

    # Additional Business Info
    pain_points = Column(ARRAY(String(255)))                # What problems they want to solve
    budget_range = Column(String(50))                        # 'under_100k', '100k_500k', '500k_1m', 'over_1m'
    timeline = Column(String(50))                           # 'immediate', '3_months', '6_months', '1_year', 'researching'

    # CRM Integration
    crm_id = Column(String(100))                             # External CRM system ID
    sales_notes = Column(Text)                               # Notes for sales team

    # Metadata
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "lead_status IN ('interested', 'qualified', 'converted', 'nurturing')",
            name='chk_lead_status'
        ),
        CheckConstraint(
            "expertise_level IN ('beginner', 'intermediate', 'expert', 'business_owner')",
            name='chk_expertise_level'
        ),
        CheckConstraint(
            "business_focus IN ('law_firm', 'corporate', 'startup', 'consulting', 'other')",
            name='chk_business_focus'
        ),
        CheckConstraint(
            "budget_range IN ('under_100k', '100k_500k', '500k_1m', 'over_1m')",
            name='chk_budget_range'
        ),
        CheckConstraint(
            "timeline IN ('immediate', '3_months', '6_months', '1_year', 'researching')",
            name='chk_timeline'
        ),
        CheckConstraint(
            "lead_score >= 0 AND lead_score <= 100",
            name='chk_lead_score_range'
        ),
    )


# ====================
# Database Connection
# ====================

# Create async engine
# КРИТИЧНО: Используем NullPool для совместимости с Celery worker
# NullPool не кэширует соединения и закрывает их сразу после использования
# Это предотвращает RuntimeError: Event loop is closed при garbage collection
from sqlalchemy.pool import NullPool

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    poolclass=NullPool,  # Используем NullPool вместо обычного пула
    connect_args={
        "server_settings": {"jit": "off"},  # Отключаем JIT для стабильности
        "command_timeout": 60,  # Таймаут команд 60 секунд
    }
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.

    Usage:
        async def some_function(db: AsyncSession = Depends(get_db)):
            # Perform database operations
            await db.commit()  # Explicit commit when needed
            ...

    Note: Caller must explicitly commit transactions.
    Auto-commit removed to prevent partial data loss on errors.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


# ====================
# Database Utilities
# ====================

async def check_db_connection() -> bool:
    """
    Check if database connection is alive.

    Returns:
        bool: True if connection is successful, False otherwise.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


async def log_to_db(
    level: str,
    message: str,
    context: Optional[dict] = None,
    session: Optional[AsyncSession] = None
) -> None:
    """
    Log event to database.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        context: Additional context as dictionary
        session: Optional existing session to use (для Celery tasks)
    """
    log_entry = SystemLog(
        level=level,
        message=message,
        context=context or {}
    )

    if session:
        # Используем переданную сессию (для Celery tasks)
        session.add(log_entry)
        await session.flush()  # Не делаем commit - это ответственность вызывающего кода
    else:
        # Создаём свою сессию (для bot handlers и других мест)
        async with AsyncSessionLocal() as db_session:
            db_session.add(log_entry)
            await db_session.commit()
