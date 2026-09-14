"""Immutable acts, acceptance and objections independent of payment."""

import sqlalchemy as sa
from alembic import op

revision = "20260913_0028"
down_revision = "20260913_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, kind in (
        ("document_text", sa.Text()), ("document_hash", sa.String(64)),
        ("document_version", sa.String(32)), ("viewed_at", sa.DateTime(timezone=True)),
        ("accepted_at", sa.DateTime(timezone=True)), ("accepted_by_telegram_user_id", sa.BigInteger()),
        ("acceptance_callback_id", sa.String(255)), ("objection_text", sa.Text()),
        ("objected_at", sa.DateTime(timezone=True)), ("cancelled_at", sa.DateTime(timezone=True)),
        ("cancel_reason", sa.String(1000)),
    ):
        op.add_column("work_acts", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    if op.get_bind().execute(sa.text(
        "SELECT 1 FROM work_acts WHERE accepted_at IS NOT NULL OR objected_at IS NOT NULL LIMIT 1"
    )).first():
        raise RuntimeError("Cannot discard recorded client acceptance or objections")
    for name in (
        "document_text", "document_hash", "document_version", "viewed_at", "accepted_at",
        "accepted_by_telegram_user_id", "acceptance_callback_id", "objection_text",
        "objected_at", "cancelled_at", "cancel_reason",
    ):
        op.drop_column("work_acts", name)
