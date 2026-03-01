from __future__ import annotations

"""Initial schema for legal-ai core API."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260225_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    scope_enum = postgresql.ENUM("bot", "news", "worker", "admin", name="scope_enum", create_type=False)
    user_role_enum = postgresql.ENUM("admin", "operator", "user", name="user_role_enum", create_type=False)
    lead_source_enum = postgresql.ENUM(
        "telegram_bot", "website_form", "telegram_channel", name="lead_source_enum", create_type=False
    )
    lead_segment_enum = postgresql.ENUM(
        "inhouse", "law_firm", "entrepreneur", "other", name="lead_segment_enum", create_type=False
    )
    lead_status_enum = postgresql.ENUM(
        "new", "qualified", "booked", "proposal", "won", "lost", name="lead_status_enum", create_type=False
    )
    scheduled_post_status_enum = postgresql.ENUM(
        "draft", "review", "scheduled", "publishing", "posted", "failed", name="scheduled_post_status_enum", create_type=False
    )
    contract_job_status_enum = postgresql.ENUM(
        "new", "processing", "done", "failed", name="contract_job_status_enum", create_type=False
    )
    input_mode_enum = postgresql.ENUM(
        "text_only", "file_url", "file_upload_reference", name="input_mode_enum", create_type=False
    )
    actor_type_enum = postgresql.ENUM("user", "api_key", "system", name="actor_type_enum", create_type=False)

    bind = op.get_bind()
    scope_enum.create(bind, checkfirst=True)
    user_role_enum.create(bind, checkfirst=True)
    lead_source_enum.create(bind, checkfirst=True)
    lead_segment_enum.create(bind, checkfirst=True)
    lead_status_enum.create(bind, checkfirst=True)
    scheduled_post_status_enum.create(bind, checkfirst=True)
    contract_job_status_enum.create(bind, checkfirst=True)
    input_mode_enum.create(bind, checkfirst=True)
    actor_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("scope", scope_enum, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
    )

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source", lead_source_enum, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("contact", sa.Text(), nullable=True),
        sa.Column("segment", lead_segment_enum, nullable=True),
        sa.Column("status", lead_status_enum, server_default=sa.text("'new'"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("utm_source", sa.String(length=255), nullable=True),
        sa.Column("utm_medium", sa.String(length=255), nullable=True),
        sa.Column("utm_campaign", sa.String(length=255), nullable=True),
        sa.Column("utm_content", sa.String(length=255), nullable=True),
        sa.Column("utm_term", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )

    op.create_table(
        "scheduled_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("channel_id", sa.String(length=255), nullable=True),
        sa.Column("channel_username", sa.String(length=255), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("media_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("rubric", sa.String(length=100), nullable=True),
        sa.Column("publish_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", scheduled_post_status_enum, server_default=sa.text("'scheduled'"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
    )

    op.create_table(
        "contract_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("status", contract_job_status_enum, server_default=sa.text("'new'"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_mode", input_mode_enum, nullable=False),
        sa.Column("document_name", sa.Text(), nullable=True),
        sa.Column("document_text", sa.Text(), nullable=True),
        sa.Column("document_url", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("report_url", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_type", actor_type_enum, nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("key_hash", name="uq_idempotency_keys_key_hash"),
    )

    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_index("ix_leads_last_activity_at", "leads", ["last_activity_at"], unique=False)
    op.create_index(
        "ix_leads_telegram_user_id",
        "leads",
        ["telegram_user_id"],
        unique=False,
        postgresql_where=sa.text("telegram_user_id IS NOT NULL"),
    )
    op.create_index("ix_leads_status", "leads", ["status"], unique=False)

    op.create_index(
        "ix_events_lead_id",
        "events",
        ["lead_id"],
        unique=False,
        postgresql_where=sa.text("lead_id IS NOT NULL"),
    )
    op.create_index("ix_events_created_at", "events", ["created_at"], unique=False)

    op.create_index(
        "ix_scheduled_posts_publish",
        "scheduled_posts",
        ["publish_at"],
        unique=False,
        postgresql_where=sa.text("status = 'scheduled'"),
    )
    op.create_index(
        "ix_scheduled_posts_source_hash",
        "scheduled_posts",
        ["source_hash"],
        unique=True,
        postgresql_where=sa.text("source_hash IS NOT NULL"),
    )

    op.create_index(
        "ix_contract_jobs_queue",
        "contract_jobs",
        ["priority", "created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'new'"),
    )
    op.create_index(
        "ix_contract_jobs_stale",
        "contract_jobs",
        ["updated_at"],
        unique=False,
        postgresql_where=sa.text("status = 'processing'"),
    )

    op.create_index("ix_idempotency_keys_created", "idempotency_keys", ["created_at"], unique=False)

    op.create_index("ix_audit_log_created", "audit_log", ["created_at"], unique=False)
    op.create_index("ix_audit_log_target", "audit_log", ["target_type", "target_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_log_target", table_name="audit_log")
    op.drop_index("ix_audit_log_created", table_name="audit_log")
    op.drop_index("ix_idempotency_keys_created", table_name="idempotency_keys")
    op.drop_index("ix_contract_jobs_stale", table_name="contract_jobs")
    op.drop_index("ix_contract_jobs_queue", table_name="contract_jobs")
    op.drop_index("ix_scheduled_posts_source_hash", table_name="scheduled_posts")
    op.drop_index("ix_scheduled_posts_publish", table_name="scheduled_posts")
    op.drop_index("ix_events_created_at", table_name="events")
    op.drop_index("ix_events_lead_id", table_name="events")
    op.drop_index("ix_leads_status", table_name="leads")
    op.drop_index("ix_leads_telegram_user_id", table_name="leads")
    op.drop_index("ix_leads_last_activity_at", table_name="leads")

    op.drop_table("worker_heartbeats")
    op.drop_table("idempotency_keys")
    op.drop_table("audit_log")
    op.drop_table("contract_jobs")
    op.drop_table("scheduled_posts")
    op.drop_table("events")
    op.drop_table("leads")
    op.drop_table("users")
    op.drop_table("api_keys")

    bind = op.get_bind()
    sa.Enum(name="actor_type_enum").drop(bind, checkfirst=True)
    sa.Enum(name="input_mode_enum").drop(bind, checkfirst=True)
    sa.Enum(name="contract_job_status_enum").drop(bind, checkfirst=True)
    sa.Enum(name="scheduled_post_status_enum").drop(bind, checkfirst=True)
    sa.Enum(name="lead_status_enum").drop(bind, checkfirst=True)
    sa.Enum(name="lead_segment_enum").drop(bind, checkfirst=True)
    sa.Enum(name="lead_source_enum").drop(bind, checkfirst=True)
    sa.Enum(name="user_role_enum").drop(bind, checkfirst=True)
    sa.Enum(name="scope_enum").drop(bind, checkfirst=True)
