"""Кто подписал без Telegram: учётная запись и почта подписанта.

Revision ID: 20260925_0044
Revises: 20260925_0043

Новая редакция п.6 NDA признаёт подписью и нажатие кнопки в личном кабинете
после входа через Яндекс ID. Идентификатор подписанта тогда — учётная запись и
подтверждённая Яндексом почта: их и фиксируем рядом с Telegram ID.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260925_0044"
down_revision = "20260925_0043"
branch_labels = None
depends_on = None

_TABLES = ("nda_signatures", "nda_personal_data_consents", "service_agreements")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("signer_account_id", UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("signer_email", sa.String(254), nullable=True))
    op.add_column("work_acts", sa.Column("accepted_by_account_id", UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("work_acts", "accepted_by_account_id")
    for table in _TABLES:
        op.drop_column(table, "signer_email")
        op.drop_column(table, "signer_account_id")
