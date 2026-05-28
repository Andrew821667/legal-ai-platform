"""Use bigint for Telegram user identifiers."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260528_0015"
down_revision = "20260522_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name, column_name in (
        ("users", "telegram_id"),
        ("leads", "telegram_user_id"),
        ("special_consultation_orders", "telegram_user_id"),
        ("reader_preferences", "telegram_user_id"),
        ("reader_saved_posts", "telegram_user_id"),
        ("reader_miniapp_events", "telegram_user_id"),
        ("post_feedback_signals", "telegram_user_id"),
    ):
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=table_name not in {
                "reader_preferences",
                "reader_saved_posts",
                "reader_miniapp_events",
            },
        )


def downgrade() -> None:
    for table_name, column_name in (
        ("users", "telegram_id"),
        ("leads", "telegram_user_id"),
        ("special_consultation_orders", "telegram_user_id"),
        ("reader_preferences", "telegram_user_id"),
        ("reader_saved_posts", "telegram_user_id"),
        ("reader_miniapp_events", "telegram_user_id"),
        ("post_feedback_signals", "telegram_user_id"),
    ):
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=table_name not in {
                "reader_preferences",
                "reader_saved_posts",
                "reader_miniapp_events",
            },
        )
