"""Автонапоминание клиенту о неподписанном договоре.

Revision ID: 20260925_0039
Revises: 20260925_0038

Договор уходил клиенту, и если тот отвлёкся — предложение тихо сгорало через
неделю: напомнить мог только юрист, вспомнив сам. Счётчик и время последнего
напоминания — чтобы ядро напоминало не больше двух раз и юрист видел, что
напоминание уже было.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260925_0039"
down_revision = "20260925_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_agreements",
        sa.Column("reminders_sent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "service_agreements",
        sa.Column("last_reminded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("service_agreements", "last_reminded_at")
    op.drop_column("service_agreements", "reminders_sent")
