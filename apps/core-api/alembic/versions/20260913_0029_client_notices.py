"""Durable operator notifications from client actions."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "20260913_0029"
down_revision = "20260913_0028"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("client_notices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_key", sa.String(255), nullable=False, unique=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("callback_data", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("claim_until", sa.DateTime(timezone=True)),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM client_notices WHERE delivered_at IS NULL LIMIT 1")).first():
        raise RuntimeError("Deliver pending client notifications before rollback")
    op.drop_table("client_notices")
