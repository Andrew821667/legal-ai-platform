"""Add miniapp_form to lead_source enum."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260522_0014"
down_revision = "20260316_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE lead_source_enum ADD VALUE IF NOT EXISTS 'miniapp_form'")


def downgrade() -> None:
    # PostgreSQL enum values are not removed safely in downgrade.
    pass
