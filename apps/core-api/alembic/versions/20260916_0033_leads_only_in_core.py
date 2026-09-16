"""Лиды только в ядре: номер лида выдаёт ядро, квалификация из бота — здесь же.

Revision ID: 20260916_0033
Revises: 20260915_0032

До этого лиды из Telegram жили в двух местах: SQLite бота (источник) и ядро
(зеркало). Номер лида выдавал SQLite. Теперь ядро — единственное хранилище:
номер выдаёт последовательность lead_legacy_id_seq, а два поля квалификации,
которые были только у бота (размер команды, договоров в месяц), переезжают
в таблицу лидов.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260916_0033"
down_revision = "20260915_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("team_size", sa.String(50), nullable=True))
    op.add_column("leads", sa.Column("contracts_per_month", sa.String(50), nullable=True))
    op.execute("CREATE SEQUENCE IF NOT EXISTS lead_legacy_id_seq")
    # Продолжаем нумерацию после уже известных номеров; бот при переносе
    # сдвинет её дальше, если его собственная нумерация ушла вперёд.
    op.execute(
        "SELECT setval('lead_legacy_id_seq', COALESCE((SELECT MAX(legacy_lead_id) FROM leads), 0) + 1, false)"
    )


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS lead_legacy_id_seq")
    op.drop_column("leads", "contracts_per_month")
    op.drop_column("leads", "team_size")
