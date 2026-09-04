"""Add outreach tracking to legal intakes

Отметка о первом обращении к клиенту от лица команды. Нужна, чтобы фоновая
задача не написала одному человеку дважды: она разбирает обращения пачками и
может перезапуститься на середине.

Отдельное поле причины хранит случаи, когда связаться нельзя: у обращений с
сайта нет Telegram, а бот не может написать первым тому, кто ему не писал.

Revision ID: 20260904_0017
Revises: 20260716_0016
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260904_0017"
down_revision = "20260716_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "legal_intakes",
        sa.Column("outreach_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "legal_intakes",
        sa.Column("outreach_blocked_reason", sa.String(length=64), nullable=True),
    )
    # Выборка ищет обращения, которым пора написать: без отметки об отправке и
    # без зафиксированной причины отказа. Индекс покрывает именно этот запрос.
    op.create_index(
        "ix_legal_intakes_outreach_pending",
        "legal_intakes",
        ["outreach_sent_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_legal_intakes_outreach_pending", table_name="legal_intakes")
    op.drop_column("legal_intakes", "outreach_blocked_reason")
    op.drop_column("legal_intakes", "outreach_sent_at")
