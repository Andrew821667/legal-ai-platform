"""Напоминание клиенту об оплате акта.

Revision ID: 20260925_0038
Revises: 20260925_0037

Неоплаченный акт висел без движения: юрист не видел, что срок прошёл, и
напомнить клиенту мог только вручную. Отметка времени напоминания — чтобы не
напоминать чаще раза в сутки и видеть, что оно уже было.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260925_0038"
down_revision = "20260925_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("work_acts", sa.Column("last_reminded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("work_acts", "last_reminded_at")
