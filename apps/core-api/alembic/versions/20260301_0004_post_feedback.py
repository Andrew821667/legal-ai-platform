from __future__ import annotations

"""Add scheduled post feedback storage and telegram publication metadata."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260301_0004"
down_revision: Union[str, None] = "20260226_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scheduled_posts", sa.Column("format_type", sa.String(length=50), nullable=True))
    op.add_column("scheduled_posts", sa.Column("cta_type", sa.String(length=50), nullable=True))
    op.add_column("scheduled_posts", sa.Column("telegram_message_id", sa.Integer(), nullable=True))
    op.add_column("scheduled_posts", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scheduled_posts", sa.Column("feedback_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index(
        "ix_scheduled_posts_telegram_message_id",
        "scheduled_posts",
        ["telegram_message_id"],
        unique=False,
        postgresql_where=sa.text("telegram_message_id IS NOT NULL"),
    )

    feedback_source_enum = postgresql.ENUM(
        "comment",
        "reaction_count",
        "reaction",
        name="post_feedback_source_enum",
        create_type=False,
    )
    feedback_source_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "post_feedback_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scheduled_posts.id"), nullable=False),
        sa.Column("source", feedback_source_enum, nullable=False),
        sa.Column("signal_key", sa.String(length=120), nullable=True),
        sa.Column("signal_value", sa.Integer(), server_default="0", nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("telegram_chat_id", sa.String(length=255), nullable=True),
        sa.Column("telegram_message_id", sa.Integer(), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_name", sa.String(length=255), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index("ix_post_feedback_signals_post_id", "post_feedback_signals", ["post_id"], unique=False)
    op.create_index("ix_post_feedback_signals_created_at", "post_feedback_signals", ["created_at"], unique=False)
    op.create_index(
        "ix_post_feedback_signals_message",
        "post_feedback_signals",
        ["telegram_message_id", "telegram_chat_id"],
        unique=False,
        postgresql_where=sa.text("telegram_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_post_feedback_signals_message", table_name="post_feedback_signals")
    op.drop_index("ix_post_feedback_signals_created_at", table_name="post_feedback_signals")
    op.drop_index("ix_post_feedback_signals_post_id", table_name="post_feedback_signals")
    op.drop_table("post_feedback_signals")

    feedback_source_enum = postgresql.ENUM(
        "comment",
        "reaction_count",
        "reaction",
        name="post_feedback_source_enum",
    )
    feedback_source_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_scheduled_posts_telegram_message_id", table_name="scheduled_posts")
    op.drop_column("scheduled_posts", "feedback_snapshot")
    op.drop_column("scheduled_posts", "posted_at")
    op.drop_column("scheduled_posts", "telegram_message_id")
    op.drop_column("scheduled_posts", "cta_type")
    op.drop_column("scheduled_posts", "format_type")
