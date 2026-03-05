from __future__ import annotations

"""Add worker activity log table for worker diagnostics."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260305_0008"
down_revision: Union[str, None] = "20260302_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_activity",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worker_activity_worker_time", "worker_activity", ["worker_id", "occurred_at"], unique=False)
    op.create_index("ix_worker_activity_action_time", "worker_activity", ["action", "occurred_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_worker_activity_action_time", table_name="worker_activity")
    op.drop_index("ix_worker_activity_worker_time", table_name="worker_activity")
    op.drop_table("worker_activity")
