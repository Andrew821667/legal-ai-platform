"""Учётные записи клиентов — вход без Telegram.

Revision ID: 20260925_0043
Revises: 20260925_0042

Telegram в России заблокирован: клиент без VPN не мог ни войти в кабинет, ни
получить договор. Теперь клиент — это учётная запись: подтверждённый email
(Яндекс ID) и, если есть, Telegram.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260925_0043"
down_revision = "20260925_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True, unique=True),
        sa.Column("yandex_id", sa.String(64), nullable=True, unique=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("client_accounts")
