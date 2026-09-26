"""Запрос документов у клиента списком.

Revision ID: 20260926_0047
Revises: 20260926_0046

Юрист отмечает, какие документы нужны, клиент видит список в боте и в
кабинете и загружает файл в нужный пункт, а юрист видит, чего не хватает.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260926_0047"
down_revision = "20260926_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "intake_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("legal_intakes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intake_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_document_requests_intake", "document_requests", ["intake_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_document_requests_intake", table_name="document_requests")
    op.drop_table("document_requests")
