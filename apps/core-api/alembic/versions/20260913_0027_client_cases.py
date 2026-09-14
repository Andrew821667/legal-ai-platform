"""Multiple cases per client and explicit work without an agreement.

Revision ID: 20260913_0027
Revises: 20260912_0026
"""

import sqlalchemy as sa
from alembic import op

revision = "20260913_0027"
down_revision = "20260912_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for item in sa.inspect(op.get_bind()).get_unique_constraints("legal_intakes"):
        if item["column_names"] == ["lead_id"]:
            op.drop_constraint(item["name"], "legal_intakes", type_="unique")
    op.create_index("ix_legal_intakes_lead_created", "legal_intakes", ["lead_id", "created_at"])
    op.add_column(
        "legal_intakes",
        sa.Column("without_agreement", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    # Refuse a lossy rollback once a client has several cases.
    duplicate = op.get_bind().execute(sa.text(
        "SELECT 1 FROM legal_intakes GROUP BY lead_id HAVING count(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError("Cannot restore one-case constraint: clients have multiple cases")
    op.create_unique_constraint("legal_intakes_lead_id_key", "legal_intakes", ["lead_id"])
    op.drop_column("legal_intakes", "without_agreement")
    op.drop_index("ix_legal_intakes_lead_created", table_name="legal_intakes")
