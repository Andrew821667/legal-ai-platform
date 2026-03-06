"""Add reader mini-app profile fields and event log.

Revision ID: 20260306_0010_reader_miniapp
Revises: 20260306_0009_reader_api
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260306_0010_reader_miniapp"
down_revision = "20260306_0009_reader_api"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reader_preferences",
        sa.Column("miniapp_onboarding_done", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "reader_preferences",
        sa.Column("miniapp_audience", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "reader_preferences",
        sa.Column(
            "miniapp_interests",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "reader_preferences",
        sa.Column("miniapp_goal", sa.Text(), nullable=True),
    )
    op.add_column(
        "reader_preferences",
        sa.Column("miniapp_last_action", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "reader_miniapp_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=50), server_default=sa.text("'miniapp'"), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("screen", sa.String(length=120), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reader_miniapp_events_user_created",
        "reader_miniapp_events",
        ["telegram_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_reader_miniapp_events_type_created",
        "reader_miniapp_events",
        ["event_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reader_miniapp_events_type_created", table_name="reader_miniapp_events")
    op.drop_index("ix_reader_miniapp_events_user_created", table_name="reader_miniapp_events")
    op.drop_table("reader_miniapp_events")

    op.drop_column("reader_preferences", "miniapp_last_action")
    op.drop_column("reader_preferences", "miniapp_goal")
    op.drop_column("reader_preferences", "miniapp_interests")
    op.drop_column("reader_preferences", "miniapp_audience")
    op.drop_column("reader_preferences", "miniapp_onboarding_done")
