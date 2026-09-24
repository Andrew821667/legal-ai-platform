"""Архив клиентов в рабочем месте юриста.

Revision ID: 20260924_0035
Revises: 20260924_0034

Тестовые и ненужные клиенты копились в списке без способа их убрать.
«Удалить» в карточке отправляет клиента в архив (archived_at), из архива —
восстановить или удалить совсем.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260924_0035"
down_revision = "20260924_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_leads_archived_at",
        "leads",
        ["archived_at"],
        postgresql_where=sa.text("archived_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_leads_archived_at", table_name="leads")
    op.drop_column("leads", "archived_at")
