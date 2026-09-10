"""Календарный срок обращения рядом со словами клиента.

Колонка `deadline` остаётся текстовой намеренно: там лежит то, как клиент
сформулировал срок сам («к этому четвергу»), и это свидетельство, а не
служебное поле — разбирать его в дату задним числом значит подменять сказанное
догадкой. `deadline_at` — то, что юрист проставил осознанно, и только по нему
строятся напоминания.

Revision ID: 20260911_0022
Revises: 20260907_0021
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260911_0022"
down_revision = "20260907_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "legal_intakes",
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("legal_intakes", "deadline_at")
