"""Add legal-help intake workflow."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260716_0016"
down_revision = "20260528_0015"
branch_labels = None
depends_on = None


client_type = postgresql.ENUM(
    "company",
    "entrepreneur",
    "individual",
    "unknown",
    name="legal_client_type_enum",
    create_type=False,
)
legal_area = postgresql.ENUM(
    "contracts",
    "disputes",
    "corporate",
    "employment",
    "tax_compliance",
    "real_estate",
    "it_ip_data",
    "family_inheritance",
    "debt_bankruptcy",
    "other",
    name="legal_area_enum",
    create_type=False,
)
urgency = postgresql.ENUM(
    "urgent",
    "high",
    "normal",
    "no_deadline",
    name="legal_urgency_enum",
    create_type=False,
)
intake_status = postgresql.ENUM(
    "received",
    "needs_clarification",
    "conflict_check",
    "scope_preparation",
    "proposal_sent",
    "accepted",
    "declined",
    "closed",
    name="legal_intake_status_enum",
    create_type=False,
)
conflict_status = postgresql.ENUM(
    "unchecked",
    "clear",
    "potential",
    "conflict",
    name="conflict_check_status_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (client_type, legal_area, urgency, intake_status, conflict_status):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "legal_intakes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("client_type", client_type, server_default="unknown", nullable=False),
        sa.Column("legal_area", legal_area, server_default="other", nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("urgency", urgency, server_default="no_deadline", nullable=False),
        sa.Column("deadline", sa.String(length=255), nullable=True),
        sa.Column("region", sa.String(length=255), nullable=True),
        sa.Column("source_context", sa.String(length=255), nullable=True),
        sa.Column("status", intake_status, server_default="received", nullable=False),
        sa.Column("conflict_status", conflict_status, server_default="unchecked", nullable=False),
        sa.Column("assigned_to", sa.String(length=255), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_id"),
    )
    op.create_index("ix_legal_intakes_status_created", "legal_intakes", ["status", "created_at"])
    op.create_index("ix_legal_intakes_urgency_created", "legal_intakes", ["urgency", "created_at"])
    op.create_index("ix_legal_intakes_area", "legal_intakes", ["legal_area"])


def downgrade() -> None:
    op.drop_index("ix_legal_intakes_area", table_name="legal_intakes")
    op.drop_index("ix_legal_intakes_urgency_created", table_name="legal_intakes")
    op.drop_index("ix_legal_intakes_status_created", table_name="legal_intakes")
    op.drop_table("legal_intakes")

    bind = op.get_bind()
    for enum_type in (conflict_status, intake_status, urgency, legal_area, client_type):
        enum_type.drop(bind, checkfirst=True)
