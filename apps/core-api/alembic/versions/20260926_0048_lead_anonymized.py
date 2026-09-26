"""Отметка об обезличивании клиента по сроку хранения (152-ФЗ).

Revision ID: 20260926_0048
Revises: 20260926_0047

Персональные данные клиентов без договора хранились бессрочно, хотя
политика обещает «не более 3 лет» и уничтожение или обезличивание по сроку.
Отметка нужна, чтобы обезличенное не обрабатывалось второй раз и было видно,
когда это случилось (см. core_api/anonymization.py).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260926_0048"
down_revision = "20260926_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "anonymized_at")
