"""Add ready status to scheduled posts enum."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260316_0013"
down_revision = "20260312_0012_sp_consult"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE scheduled_post_status_enum ADD VALUE IF NOT EXISTS 'ready'")


def downgrade() -> None:
    # PostgreSQL enum values are not removed safely in downgrade.
    pass
