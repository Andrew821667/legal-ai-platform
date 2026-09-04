"""Ответы клиента на уточняющие вопросы и присланные им документы.

Revision ID: 20260904_0019
Revises: 20260904_0018
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260904_0019"
down_revision = "20260904_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intake_clarifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "intake_id",
            UUID(as_uuid=True),
            sa.ForeignKey("legal_intakes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("question_key", sa.String(64), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.UniqueConstraint("intake_id", "question_key", name="uq_intake_clarification_question"),
    )
    op.create_index(
        "ix_intake_clarifications_intake",
        "intake_clarifications",
        ["intake_id", "created_at"],
    )

    op.create_table(
        "intake_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "intake_id",
            UUID(as_uuid=True),
            sa.ForeignKey("legal_intakes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("telegram_file_id", sa.String(255), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column(
            "nda_signed_at_upload",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_intake_documents_intake",
        "intake_documents",
        ["intake_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_intake_documents_intake", table_name="intake_documents")
    op.drop_table("intake_documents")
    op.drop_index("ix_intake_clarifications_intake", table_name="intake_clarifications")
    op.drop_table("intake_clarifications")
