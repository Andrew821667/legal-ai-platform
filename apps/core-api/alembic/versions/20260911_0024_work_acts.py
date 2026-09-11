"""Акт выполненных работ по подписанному договору.

Revision ID: 20260911_0024
Revises: 20260911_0023
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

revision = "20260911_0024"
down_revision = "20260911_0023"
branch_labels = None
depends_on = None

_STATUS_NAME = "work_act_status_enum"
_STATUS_VALUES = ("draft", "sent", "claimed_paid", "paid")

_STATUS = sa.Enum(*_STATUS_VALUES, name=_STATUS_NAME)
_STATUS_REF = ENUM(*_STATUS_VALUES, name=_STATUS_NAME, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    _STATUS.create(bind, checkfirst=True)

    op.create_table(
        "work_acts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("act_number", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "agreement_id",
            UUID(as_uuid=True),
            sa.ForeignKey("service_agreements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status", _STATUS_REF, server_default="draft", nullable=False),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="RUB", nullable=False),
        sa.Column("prepared_by_telegram_user_id", sa.BigInteger()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("sent_chat_id", sa.BigInteger()),
        sa.Column("sent_message_id", sa.BigInteger()),
        sa.Column("claimed_paid_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("paid_by_telegram_user_id", sa.BigInteger()),
        sa.Column("paid_note", sa.String(500)),
    )
    op.create_index("ix_work_acts_agreement", "work_acts", ["agreement_id", "created_at"])
    op.create_index("ix_work_acts_lead", "work_acts", ["lead_id", "created_at"])
    op.create_index("ix_work_acts_status", "work_acts", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_work_acts_status", table_name="work_acts")
    op.drop_index("ix_work_acts_lead", table_name="work_acts")
    op.drop_index("ix_work_acts_agreement", table_name="work_acts")
    op.drop_table("work_acts")
    _STATUS.drop(op.get_bind(), checkfirst=True)
