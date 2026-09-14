"""Record signer identity and separate personal-data consent."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260914_0031"
down_revision = "20260913_0030"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "nda_personal_data_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(255), nullable=True),
        sa.Column("signer_full_name", sa.String(255), nullable=False),
        sa.Column("signer_contact", sa.String(255), nullable=False),
        sa.Column("signer_org", sa.String(500), nullable=True),
        sa.Column("signer_identity_document", sa.String(500), nullable=False),
        sa.Column("document_version", sa.String(100), nullable=False),
        sa.Column("document_hash", sa.String(64), nullable=False),
        sa.Column("document_text", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nda_pdn_consents_lead", "nda_personal_data_consents", ["lead_id"])
    op.create_index(
        "ix_nda_pdn_consents_accepted_at", "nda_personal_data_consents", ["accepted_at"]
    )
    op.add_column(
        "nda_signatures",
        sa.Column("signer_identity_document", sa.String(500), nullable=True),
    )
    op.add_column(
        "nda_signatures",
        sa.Column("pdn_consent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_nda_signatures_pdn_consent",
        "nda_signatures",
        "nda_personal_data_consents",
        ["pdn_consent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_nda_signatures_pdn_consent", "nda_signatures", type_="foreignkey")
    op.drop_column("nda_signatures", "pdn_consent_id")
    op.drop_column("nda_signatures", "signer_identity_document")
    op.drop_index("ix_nda_pdn_consents_accepted_at", table_name="nda_personal_data_consents")
    op.drop_index("ix_nda_pdn_consents_lead", table_name="nda_personal_data_consents")
    op.drop_table("nda_personal_data_consents")
