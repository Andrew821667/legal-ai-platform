"""Переписка по делу в кабинете: клиент ↔ юрист.

Revision ID: 20261001_0054
Revises: 20261001_0053

Клиент без Telegram (вход через Яндекс ID) не мог написать юристу и получить
ответ: «Написать по делу» вела в бота, а ответ юриста на вопрос по договору
падал с «у клиента нет Telegram». Общий тред по делу живёт здесь.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20261001_0054"
down_revision = "20261001_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "intake_id", UUID(as_uuid=True), sa.ForeignKey("legal_intakes.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("author", sa.String(16), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_case_messages_lead", "case_messages", ["lead_id", "created_at"])
    op.create_index("ix_case_messages_intake", "case_messages", ["intake_id"])


def downgrade() -> None:
    op.drop_index("ix_case_messages_intake", table_name="case_messages")
    op.drop_index("ix_case_messages_lead", table_name="case_messages")
    op.drop_table("case_messages")
