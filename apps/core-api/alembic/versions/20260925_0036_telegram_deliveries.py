"""Журнал отправок ядра в Telegram и состояние связи.

Revision ID: 20260925_0036
Revises: 20260924_0035

Ядро отправляло договоры, акты и уведомления без прокси, и сбои оседали в
логе: юрист узнал о них, только нажав «Отправить». Теперь у каждой отправки
есть исход, фоновые повторяются, а о пропавшей связи сообщают.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260925_0036"
down_revision = "20260924_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("chat_id", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("reply_markup", sa.Text(), nullable=True),
        sa.Column("parse_mode", sa.String(16), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("act_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_telegram_deliveries_due", "telegram_deliveries", ["status", "next_attempt_at"])
    op.create_index("ix_telegram_deliveries_lead", "telegram_deliveries", ["lead_id"])
    op.create_table(
        "service_health",
        sa.Column("key", sa.String(64), primary_key=True, nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failing_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("service_health")
    op.drop_index("ix_telegram_deliveries_lead", table_name="telegram_deliveries")
    op.drop_index("ix_telegram_deliveries_due", table_name="telegram_deliveries")
    op.drop_table("telegram_deliveries")
