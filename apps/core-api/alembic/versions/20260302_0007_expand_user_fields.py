from __future__ import annotations

"""Expand core user model for consent and admin migration."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260302_0007"
down_revision: Union[str, None] = "20260302_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("first_name", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("consent_given", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("consent_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("consent_revoked", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("consent_revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("transborder_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("transborder_consent_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("marketing_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("marketing_consent_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("conversation_stage", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("cta_variant", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("cta_shown", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("cta_shown_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_interaction", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "ix_users_telegram_id",
        "users",
        ["telegram_id"],
        unique=True,
        postgresql_where=sa.text("telegram_id IS NOT NULL"),
    )
    op.create_index("ix_users_last_interaction", "users", ["last_interaction"], unique=False)
    op.create_index("ix_users_consent_revoked", "users", ["consent_revoked"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_consent_revoked", table_name="users")
    op.drop_index("ix_users_last_interaction", table_name="users")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_column("users", "last_interaction")
    op.drop_column("users", "cta_shown_at")
    op.drop_column("users", "cta_shown")
    op.drop_column("users", "cta_variant")
    op.drop_column("users", "conversation_stage")
    op.drop_column("users", "marketing_consent_date")
    op.drop_column("users", "marketing_consent")
    op.drop_column("users", "transborder_consent_date")
    op.drop_column("users", "transborder_consent")
    op.drop_column("users", "consent_revoked_at")
    op.drop_column("users", "consent_revoked")
    op.drop_column("users", "consent_date")
    op.drop_column("users", "consent_given")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "username")
