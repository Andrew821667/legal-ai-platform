"""Чек самозанятого («Мой налог») по оплаченному акту.

Revision ID: 20260925_0040
Revises: 20260925_0039

Самозанятый обязан выдать покупателю чек при расчёте, в том числе в
электронном виде. Система знала об оплате, но не о чеке: держалось всё на
памяти юриста. Ссылка или номер чека, когда он выдан и когда отправлен
клиенту.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260925_0040"
down_revision = "20260925_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("work_acts", sa.Column("receipt_ref", sa.String(500), nullable=True))
    op.add_column("work_acts", sa.Column("receipt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("work_acts", sa.Column("receipt_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("work_acts", "receipt_sent_at")
    op.drop_column("work_acts", "receipt_at")
    op.drop_column("work_acts", "receipt_ref")
