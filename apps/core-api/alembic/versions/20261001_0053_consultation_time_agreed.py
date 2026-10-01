"""Консультация: оплатить сейчас, время согласовать.

Revision ID: 20261001_0053
Revises: 20260930_0052

Решение владельца 01.10.2026: время консультации — по договорённости с
клиентом. Раньше без свободного времени в расписании оплатить консультацию
было нельзя: бронь существовала только вместе с временем. Теперь бронь может
быть без времени (starts_at пусто) — юрист назначает его после разговора.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261001_0053"
down_revision = "20260930_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("consultation_slots", "starts_at", existing_type=sa.DateTime(timezone=True), nullable=True)


def downgrade() -> None:
    # Брони без времени при откате закрываются: колонка снова обязательна.
    op.execute(
        "UPDATE consultation_slots SET starts_at = created_at, status = 'cancelled', cancelled_at = now() "
        "WHERE starts_at IS NULL"
    )
    op.alter_column("consultation_slots", "starts_at", existing_type=sa.DateTime(timezone=True), nullable=False)
