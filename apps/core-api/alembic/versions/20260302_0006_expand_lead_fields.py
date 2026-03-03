from __future__ import annotations

"""Expand core lead model for legacy admin migration."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260302_0006"
down_revision: Union[str, None] = "20260301_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("legacy_lead_id", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("company", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("email", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("temperature", sa.String(length=20), nullable=True))
    op.add_column("leads", sa.Column("service_category", sa.String(length=255), nullable=True))
    op.add_column("leads", sa.Column("specific_need", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("pain_point", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("budget", sa.String(length=255), nullable=True))
    op.add_column("leads", sa.Column("urgency", sa.String(length=255), nullable=True))
    op.add_column("leads", sa.Column("industry", sa.String(length=255), nullable=True))
    op.add_column("leads", sa.Column("conversation_stage", sa.String(length=50), nullable=True))
    op.add_column("leads", sa.Column("cta_variant", sa.String(length=50), nullable=True))
    op.add_column("leads", sa.Column("cta_shown", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("leads", sa.Column("lead_magnet_type", sa.String(length=255), nullable=True))
    op.add_column(
        "leads",
        sa.Column("lead_magnet_delivered", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    op.create_index(
        "ix_leads_legacy_lead_id",
        "leads",
        ["legacy_lead_id"],
        unique=True,
        postgresql_where=sa.text("legacy_lead_id IS NOT NULL"),
    )
    op.create_index("ix_leads_temperature", "leads", ["temperature"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_leads_temperature", table_name="leads")
    op.drop_index("ix_leads_legacy_lead_id", table_name="leads")
    op.drop_column("leads", "lead_magnet_delivered")
    op.drop_column("leads", "lead_magnet_type")
    op.drop_column("leads", "cta_shown")
    op.drop_column("leads", "cta_variant")
    op.drop_column("leads", "conversation_stage")
    op.drop_column("leads", "industry")
    op.drop_column("leads", "urgency")
    op.drop_column("leads", "budget")
    op.drop_column("leads", "pain_point")
    op.drop_column("leads", "specific_need")
    op.drop_column("leads", "service_category")
    op.drop_column("leads", "temperature")
    op.drop_column("leads", "phone")
    op.drop_column("leads", "email")
    op.drop_column("leads", "company")
    op.drop_column("leads", "legacy_lead_id")
