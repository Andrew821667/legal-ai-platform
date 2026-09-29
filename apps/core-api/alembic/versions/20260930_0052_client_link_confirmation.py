"""Объединение с Telegram — только после подтверждения в Telegram.

Revision ID: 20260930_0052
Revises: 20260929_0051

Код из бота, введённый на сайте, больше не объединяет сразу: он закрепляется
за учётной записью (claimed_account_id), и бот спрашивает владельца Telegram,
объединить ли его с этой почтой. Владелец видит, с чем именно объединяется.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260930_0052"
down_revision = "20260929_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_link_codes",
        sa.Column(
            "claimed_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("client_accounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column("client_link_codes", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("client_link_codes", "claimed_at")
    op.drop_column("client_link_codes", "claimed_account_id")
