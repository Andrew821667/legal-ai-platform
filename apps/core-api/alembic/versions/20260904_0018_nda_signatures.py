"""Add NDA signatures

Подписание соглашения о конфиденциальности простой электронной подписью.
Фиксируются обстоятельства: кто, когда и какой именно текст видел. Хеш текста
доказывает, что документ не менялся после подписания.

Одна запись на клиента: подписанное соглашение действует на все обращения.

Revision ID: 20260904_0018
Revises: 20260904_0017
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260904_0018"
down_revision = "20260904_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nda_signatures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("signer_name", sa.String(length=255), nullable=True),
        sa.Column("document_version", sa.String(length=32), nullable=False),
        sa.Column("document_hash", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="telegram_bot"),
    )
    op.create_index("ix_nda_signatures_lead", "nda_signatures", ["lead_id"])
    op.create_index("ix_nda_signatures_signed_at", "nda_signatures", ["signed_at"])


def downgrade() -> None:
    op.drop_index("ix_nda_signatures_signed_at", table_name="nda_signatures")
    op.drop_index("ix_nda_signatures_lead", table_name="nda_signatures")
    op.drop_table("nda_signatures")
