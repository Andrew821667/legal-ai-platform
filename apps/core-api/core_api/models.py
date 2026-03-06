from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func, text as sa_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core_api.db import Base


class Scope(str, enum.Enum):
    bot = "bot"
    news = "news"
    worker = "worker"
    admin = "admin"


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    user = "user"


class LeadSource(str, enum.Enum):
    telegram_bot = "telegram_bot"
    website_form = "website_form"
    telegram_channel = "telegram_channel"


class LeadSegment(str, enum.Enum):
    inhouse = "inhouse"
    law_firm = "law_firm"
    entrepreneur = "entrepreneur"
    other = "other"


class LeadStatus(str, enum.Enum):
    new = "new"
    qualified = "qualified"
    booked = "booked"
    proposal = "proposal"
    won = "won"
    lost = "lost"


class ScheduledPostStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    scheduled = "scheduled"
    publishing = "publishing"
    posted = "posted"
    failed = "failed"


class PostFeedbackSource(str, enum.Enum):
    comment = "comment"
    reaction_count = "reaction_count"
    reaction = "reaction"


class ContractJobStatus(str, enum.Enum):
    new = "new"
    processing = "processing"
    done = "done"
    failed = "failed"


class InputMode(str, enum.Enum):
    text_only = "text_only"
    file_url = "file_url"
    file_upload_reference = "file_upload_reference"


class ActorType(str, enum.Enum):
    user = "user"
    api_key = "api_key"
    system = "system"


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[Scope] = mapped_column(Enum(Scope, name="scope_enum"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa_text("true"))


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role_enum"), nullable=False)
    telegram_id: Mapped[int | None] = mapped_column(nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    consent_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_revoked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false")
    )
    consent_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transborder_consent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false")
    )
    transborder_consent_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    marketing_consent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false")
    )
    marketing_consent_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    conversation_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cta_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cta_shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    cta_shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_interaction: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_users_telegram_id",
            "telegram_id",
            unique=True,
            postgresql_where=sa_text("telegram_id IS NOT NULL"),
        ),
        Index("ix_users_last_interaction", "last_interaction"),
        Index("ix_users_consent_revoked", "consent_revoked"),
    )


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source: Mapped[LeadSource] = mapped_column(Enum(LeadSource, name="lead_source_enum"), nullable=False)
    legacy_lead_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    segment: Mapped[LeadSegment | None] = mapped_column(
        Enum(LeadSegment, name="lead_segment_enum"), nullable=True
    )
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status_enum"), nullable=False, default=LeadStatus.new
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature: Mapped[str | None] = mapped_column(String(20), nullable=True)
    service_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specific_need: Mapped[str | None] = mapped_column(Text, nullable=True)
    pain_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget: Mapped[str | None] = mapped_column(String(255), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    conversation_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cta_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cta_shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    lead_magnet_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead_magnet_delivered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_leads_last_activity_at", "last_activity_at"),
        Index(
            "ix_leads_legacy_lead_id",
            "legacy_lead_id",
            unique=True,
            postgresql_where=sa_text("legacy_lead_id IS NOT NULL"),
        ),
        Index(
            "ix_leads_telegram_user_id",
            "telegram_user_id",
            postgresql_where=sa_text("telegram_user_id IS NOT NULL"),
        ),
        Index("ix_leads_status", "status"),
        Index("ix_leads_temperature", "temperature"),
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_events_lead_id", "lead_id", postgresql_where=sa_text("lead_id IS NOT NULL")),
        Index("ix_events_created_at", "created_at"),
    )


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rubric: Mapped[str | None] = mapped_column(String(100), nullable=True)
    format_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cta_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ScheduledPostStatus] = mapped_column(
        Enum(ScheduledPostStatus, name="scheduled_post_status_enum"),
        nullable=False,
        default=ScheduledPostStatus.scheduled,
    )
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_scheduled_posts_publish",
            "publish_at",
            postgresql_where=sa_text("status = 'scheduled'"),
        ),
        Index(
            "ix_scheduled_posts_source_hash",
            "source_hash",
            unique=True,
            postgresql_where=sa_text("source_hash IS NOT NULL"),
        ),
        Index(
            "ix_scheduled_posts_telegram_message_id",
            "telegram_message_id",
            postgresql_where=sa_text("telegram_message_id IS NOT NULL"),
        ),
    )


class ReaderPreference(Base):
    __tablename__ = "reader_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    telegram_user_id: Mapped[int] = mapped_column(nullable=False)
    topics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default=sa_text("'[]'::jsonb"))
    digest_frequency: Mapped[str] = mapped_column(
        String(50), nullable=False, default="never", server_default=sa_text("'never'")
    )
    expertise_level: Mapped[str | None] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_reader_preferences_telegram_user_id", "telegram_user_id", unique=True),
    )


class ReaderSavedPost(Base):
    __tablename__ = "reader_saved_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    telegram_user_id: Mapped[int] = mapped_column(nullable=False)
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduled_posts.id"), nullable=False)

    __table_args__ = (
        Index("ix_reader_saved_posts_user_created", "telegram_user_id", "created_at"),
        Index("ix_reader_saved_posts_post_id", "post_id"),
        Index("ux_reader_saved_posts_user_post", "telegram_user_id", "post_id", unique=True),
    )


class PostFeedbackSignal(Base):
    __tablename__ = "post_feedback_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scheduled_posts.id"), nullable=False)
    source: Mapped[PostFeedbackSource] = mapped_column(
        Enum(PostFeedbackSource, name="post_feedback_source_enum"),
        nullable=False,
    )
    signal_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    signal_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_post_feedback_signals_post_id", "post_id"),
        Index("ix_post_feedback_signals_created_at", "created_at"),
        Index(
            "ix_post_feedback_signals_message",
            "telegram_message_id",
            "telegram_chat_id",
            postgresql_where=sa_text("telegram_message_id IS NOT NULL"),
        ),
    )


class ContractJob(Base):
    __tablename__ = "contract_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ContractJobStatus] = mapped_column(
        Enum(ContractJobStatus, name="contract_job_status_enum"),
        nullable=False,
        default=ContractJobStatus.new,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_mode: Mapped[InputMode] = mapped_column(Enum(InputMode, name="input_mode_enum"), nullable=False)
    document_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_contract_jobs_queue",
            "priority",
            "created_at",
            postgresql_where=sa_text("status = 'new'"),
        ),
        Index(
            "ix_contract_jobs_stale",
            "updated_at",
            postgresql_where=sa_text("status = 'processing'"),
        ),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType, name="actor_type_enum"), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_audit_log_created", "created_at"),
        Index("ix_audit_log_target", "target_type", "target_id"),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (Index("ix_idempotency_keys_created", "created_at"),)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    info: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class WorkerActivity(Base):
    __tablename__ = "worker_activity"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_worker_activity_worker_time", "worker_id", "occurred_at"),
        Index("ix_worker_activity_action_time", "action", "occurred_at"),
    )


class AutomationControl(Base):
    __tablename__ = "automation_controls"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    scope: Mapped[Scope | None] = mapped_column(Enum(Scope, name="scope_enum"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa_text("true"))
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=sa_text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (Index("ix_automation_controls_scope", "scope"),)
