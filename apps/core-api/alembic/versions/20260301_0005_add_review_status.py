"""Add review status to scheduled posts enum."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260301_0005"
down_revision = "20260301_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE scheduled_post_status_enum ADD VALUE IF NOT EXISTS 'review'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely in-place.
    pass
