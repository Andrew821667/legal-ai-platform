"""Объединение учётной записи сайта (Яндекс ID) с Telegram по согласию клиента.

Revision ID: 20260929_0051
Revises: 20260929_0050

Клиент, который вёл дела в Telegram-боте, входит на сайт через Яндекс ID и
видит пустой кабинет. Привязка — только с доказательством владения обоими
входами: бот выдаёт владельцу Telegram одноразовый код, клиент вводит его в
кабинете (client_link_codes); либо в одном браузере открыты обе сессии.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260929_0051"
down_revision = "20260929_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_accounts", sa.Column("telegram_username", sa.String(255), nullable=True))
    op.add_column("client_accounts", sa.Column("telegram_linked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "client_link_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(255), nullable=True),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_client_link_codes_telegram_user_id", "client_link_codes", ["telegram_user_id"])


def downgrade() -> None:
    op.drop_index("ix_client_link_codes_telegram_user_id", table_name="client_link_codes")
    op.drop_table("client_link_codes")
    op.drop_column("client_accounts", "telegram_linked_at")
    op.drop_column("client_accounts", "telegram_username")
