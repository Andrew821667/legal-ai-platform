"""Связь между обращениями двух разных клиентов по одному фактическому делу.

Revision ID: 20260912_0025
Revises: 20260911_0024
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

revision = "20260912_0025"
down_revision = "20260911_0024"
branch_labels = None
depends_on = None

_TYPE_NAME = "intake_link_type_enum"
_TYPE_VALUES = ("subordinate", "joint")

_TYPE = sa.Enum(*_TYPE_VALUES, name=_TYPE_NAME)
_TYPE_REF = ENUM(*_TYPE_VALUES, name=_TYPE_NAME, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    _TYPE.create(bind, checkfirst=True)

    op.create_table(
        "intake_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "intake_id",
            UUID(as_uuid=True),
            sa.ForeignKey("legal_intakes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "linked_intake_id",
            UUID(as_uuid=True),
            sa.ForeignKey("legal_intakes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("link_type", _TYPE_REF, nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by_telegram_user_id", sa.BigInteger()),
    )
    op.create_index("ix_intake_links_intake", "intake_links", ["intake_id"])
    op.create_index("ix_intake_links_linked_intake", "intake_links", ["linked_intake_id"])


def downgrade() -> None:
    op.drop_index("ix_intake_links_linked_intake", table_name="intake_links")
    op.drop_index("ix_intake_links_intake", table_name="intake_links")
    op.drop_table("intake_links")
    _TYPE.drop(op.get_bind(), checkfirst=True)
