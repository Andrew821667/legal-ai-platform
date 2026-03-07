"""Add reader rollup table and performance indexes.

Revision ID: 20260307_0011_reader_rollup
Revises: 20260306_0010_reader_miniapp
Create Date: 2026-03-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_0011_reader_rollup"
down_revision = "20260306_0010_reader_miniapp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reader_event_rollups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=120), server_default=sa.text("''"), nullable=False),
        sa.Column("cta_variant", sa.String(length=50), server_default=sa.text("'v1_direct'"), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_reader_event_rollups_bucket_dims",
        "reader_event_rollups",
        ["bucket_start", "channel", "source", "action", "cta_variant"],
        unique=True,
    )
    op.create_index(
        "ix_reader_event_rollups_bucket_channel",
        "reader_event_rollups",
        ["bucket_start", "channel"],
        unique=False,
    )
    op.create_index(
        "ix_reader_event_rollups_variant_bucket",
        "reader_event_rollups",
        ["cta_variant", "bucket_start"],
        unique=False,
    )

    op.create_index("ix_events_type_created_at", "events", ["type", "created_at"], unique=False)
    op.create_index(
        "ix_reader_miniapp_events_source_created",
        "reader_miniapp_events",
        ["source", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_reader_miniapp_events_action_created",
        "reader_miniapp_events",
        ["action", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reader_miniapp_events_action_created", table_name="reader_miniapp_events")
    op.drop_index("ix_reader_miniapp_events_source_created", table_name="reader_miniapp_events")
    op.drop_index("ix_events_type_created_at", table_name="events")

    op.drop_index("ix_reader_event_rollups_variant_bucket", table_name="reader_event_rollups")
    op.drop_index("ix_reader_event_rollups_bucket_channel", table_name="reader_event_rollups")
    op.drop_index("ux_reader_event_rollups_bucket_dims", table_name="reader_event_rollups")
    op.drop_table("reader_event_rollups")
