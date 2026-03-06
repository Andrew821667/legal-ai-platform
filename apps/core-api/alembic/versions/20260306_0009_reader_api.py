"""Add reader API storage tables.

Revision ID: 20260306_0009_reader_api
Revises: 20260305_0008
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260306_0009_reader_api"
down_revision = "20260305_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reader_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("digest_frequency", sa.String(length=50), server_default=sa.text("'never'"), nullable=False),
        sa.Column("expertise_level", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reader_preferences_telegram_user_id",
        "reader_preferences",
        ["telegram_user_id"],
        unique=True,
    )

    op.create_table(
        "reader_saved_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["scheduled_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reader_saved_posts_user_created",
        "reader_saved_posts",
        ["telegram_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_reader_saved_posts_post_id",
        "reader_saved_posts",
        ["post_id"],
        unique=False,
    )
    op.create_index(
        "ux_reader_saved_posts_user_post",
        "reader_saved_posts",
        ["telegram_user_id", "post_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_reader_saved_posts_user_post", table_name="reader_saved_posts")
    op.drop_index("ix_reader_saved_posts_post_id", table_name="reader_saved_posts")
    op.drop_index("ix_reader_saved_posts_user_created", table_name="reader_saved_posts")
    op.drop_table("reader_saved_posts")

    op.drop_index("ix_reader_preferences_telegram_user_id", table_name="reader_preferences")
    op.drop_table("reader_preferences")
