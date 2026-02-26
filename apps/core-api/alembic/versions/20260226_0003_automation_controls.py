from __future__ import annotations

"""Automation controls table for admin control plane."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260226_0003"
down_revision: Union[str, None] = "20260225_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    scope_enum = sa.Enum("bot", "news", "worker", "admin", name="scope_enum", create_type=False)
    op.create_table(
        "automation_controls",
        sa.Column("key", sa.String(length=120), primary_key=True, nullable=False),
        sa.Column("scope", scope_enum, nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_automation_controls_scope", "automation_controls", ["scope"], unique=False)

    op.execute(
        """
        INSERT INTO automation_controls (key, scope, title, description, enabled, config, updated_by)
        VALUES
            ('news.generate.enabled', 'news', 'Генерация контента (news.generate)', 'Ночная автогенерация контент-плана и постов из источников.', true, '{}'::jsonb, 'migration'),
            ('news.publish.enabled', 'news', 'Публикация в Telegram (news.publish)', 'Автопаблишер scheduled_posts в Telegram-канал.', true, '{}'::jsonb, 'migration'),
            ('news.digest.enabled', 'news', 'Недельный дайджест', 'Автоматическая генерация weekly digest слотов.', true, '{}'::jsonb, 'migration'),
            ('news.alert_slot.enabled', 'news', 'Вечерний alert-слот', 'Дополнительный срочный слот при high-urgency материалах.', true, '{}'::jsonb, 'migration'),
            ('lead_bot.autorespond.enabled', 'bot', 'Автоответы лид-бота', 'Автоматическая генерация ответов в лид-боте.', true, '{}'::jsonb, 'migration'),
            ('worker.autoclaim.enabled', 'worker', 'Автоклейм contract-jobs', 'Автозахват новых задач contract-worker-ом.', true, '{}'::jsonb, 'migration')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_automation_controls_scope", table_name="automation_controls")
    op.drop_table("automation_controls")
