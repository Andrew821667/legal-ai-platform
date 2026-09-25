"""Заготовки условий договора.

Revision ID: 20260925_0037
Revises: 20260925_0036

Юрист набирал предмет, объём, сроки, цену и оплату руками в каждом
договоре, хотя для типовых услуг они повторяются. Заготовка заполняет форму
договора — дальше юрист правит её под дело.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260925_0037"
down_revision = "20260925_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    practice = postgresql.ENUM(name="practice_enum", create_type=False)
    op.create_table(
        "agreement_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("practice", practice, nullable=True),
        sa.Column("subject", sa.Text(), nullable=False, server_default=""),
        sa.Column("scope_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("exclusions_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("schedule_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("price_text", sa.String(500), nullable=False, server_default=""),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("payment_terms", sa.Text(), nullable=False, server_default=""),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agreement_templates")
