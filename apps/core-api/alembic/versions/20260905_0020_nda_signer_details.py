"""Данные, которые подписант NDA вводит сам.

Revision ID: 20260905_0020
Revises: 20260904_0019
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260905_0020"
down_revision = "20260904_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nda_signatures", sa.Column("signer_full_name", sa.String(255), nullable=True))
    op.add_column("nda_signatures", sa.Column("signer_contact", sa.String(255), nullable=True))
    op.add_column("nda_signatures", sa.Column("signer_org", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("nda_signatures", "signer_org")
    op.drop_column("nda_signatures", "signer_contact")
    op.drop_column("nda_signatures", "signer_full_name")
