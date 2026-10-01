"""Файлы по делу у нас, а не в Telegram: результаты юриста и загрузки клиента.

Revision ID: 20261001_0055
Revises: 20261001_0054

Передать клиенту без Telegram результат работы было нечем, а документы,
загруженные клиентом в кабинете, пересылались юристу в Telegram и хранились
там (серверы за рубежом). Теперь файл лежит в базе в России, зашифрованным
тем же ключом, что и паспортные данные.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20261001_0055"
down_revision = "20261001_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "intake_id", UUID(as_uuid=True), sa.ForeignKey("legal_intakes.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_client_files_lead", "client_files", ["lead_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_client_files_lead", table_name="client_files")
    op.drop_table("client_files")
