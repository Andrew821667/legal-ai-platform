"""Одноразовые ссылки входа юриста: погашенные nonce.

Revision ID: 20261002_0056
Revises: 20261001_0055

Ссылка из бота раньше сама была пропуском на 30 дней: открывалась сколько
угодно раз и оседала в истории браузера и журналах. Теперь она срабатывает
один раз — сайт гасит её nonce здесь и выдаёт свою куку сессии.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261002_0056"
down_revision = "20261001_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lawyer_login_nonces",
        sa.Column("nonce_hash", sa.String(64), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lawyer_login_nonces")
