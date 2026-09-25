"""Отзывы клиентов после оплаченного акта.

Revision ID: 20260925_0041
Revises: 20260925_0040

Отзывы — главный довод для нового клиента юриста, а собирать их было нечем:
работа закончена, деньги пришли — и на этом всё. Бот через сутки после
оплаты просит оценку и пару слов; публикуется только то, на что клиент дал
согласие и что одобрил юрист.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260925_0041"
down_revision = "20260925_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("work_acts", sa.Column("review_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "client_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("act_id", UUID(as_uuid=True), sa.ForeignKey("work_acts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("publish_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("act_id", name="uq_client_reviews_act"),
        sa.CheckConstraint("score IS NULL OR score BETWEEN 1 AND 5", name="ck_client_reviews_score"),
    )
    op.create_index("ix_client_reviews_status", "client_reviews", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_client_reviews_status", table_name="client_reviews")
    op.drop_table("client_reviews")
    op.drop_column("work_acts", "review_requested_at")
