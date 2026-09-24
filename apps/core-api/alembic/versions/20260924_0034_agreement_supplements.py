"""Дополнительные соглашения к подписанному договору.

Revision ID: 20260924_0034
Revises: 20260916_0033

Сумму подписанного договора юрист менял одной кнопкой — односторонне, без
документа для клиента. Теперь новая стоимость и дополнительные работы идут
клиенту допсоглашением: это строка той же таблицы со ссылкой на основной
договор, чтобы подписание работало тем же путём, что и у договора.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260924_0034"
down_revision = "20260916_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_agreements",
        sa.Column(
            "parent_agreement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_agreements.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_service_agreements_parent",
        "service_agreements",
        ["parent_agreement_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_service_agreements_parent", table_name="service_agreements")
    op.drop_column("service_agreements", "parent_agreement_id")
