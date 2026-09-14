"""Move the working lead notification state into Core API."""
import sqlalchemy as sa
from alembic import op

revision = "20260913_0030"
down_revision = "20260913_0029"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("last_message_at", sa.DateTime(timezone=True)))
    op.add_column("leads", sa.Column("notification_sent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("leads", sa.Column("notification_sent_at", sa.DateTime(timezone=True)))
    op.create_index("ix_leads_pending_notification", "leads", ["notification_sent", "last_message_at"])


def downgrade():
    op.drop_index("ix_leads_pending_notification", table_name="leads")
    op.drop_column("leads", "notification_sent_at")
    op.drop_column("leads", "notification_sent")
    op.drop_column("leads", "last_message_at")
