"""Счёт на предоплату (аванс) по договору.

Revision ID: 20260925_0042
Revises: 20260925_0041

Деньги приходили только по акту — после работы. Аванс — тот же платёжный
документ с QR и «Я оплатил(а)», но без приёмки работы: kind='advance'.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260925_0042"
down_revision = "20260925_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("work_acts", sa.Column("kind", sa.String(16), nullable=False, server_default="act"))


def downgrade() -> None:
    op.drop_column("work_acts", "kind")
