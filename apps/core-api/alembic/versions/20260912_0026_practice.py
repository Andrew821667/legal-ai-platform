"""Направление практики на обращении и вид шаблона на договоре.

Revision ID: 20260912_0026
Revises: 20260912_0025
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

revision = "20260912_0026"
down_revision = "20260912_0025"
branch_labels = None
depends_on = None

_PRACTICE_NAME = "practice_enum"
_PRACTICE_VALUES = ("legal", "engineering", "hybrid")
_PRACTICE = sa.Enum(*_PRACTICE_VALUES, name=_PRACTICE_NAME)
_PRACTICE_REF = ENUM(*_PRACTICE_VALUES, name=_PRACTICE_NAME, create_type=False)

_KIND_NAME = "agreement_template_kind_enum"
_KIND_VALUES = ("legal_services", "software_development", "legal_automation")
_KIND = sa.Enum(*_KIND_VALUES, name=_KIND_NAME)
_KIND_REF = ENUM(*_KIND_VALUES, name=_KIND_NAME, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    _PRACTICE.create(bind, checkfirst=True)
    _KIND.create(bind, checkfirst=True)

    # Только добавляющие изменения: существующие обращения и договоры —
    # юридическая практика, как и были.
    op.add_column(
        "legal_intakes",
        sa.Column("practice", _PRACTICE_REF, server_default="legal", nullable=False),
    )
    op.add_column("legal_intakes", sa.Column("category", sa.String(64), nullable=True))
    op.create_index("ix_legal_intakes_practice", "legal_intakes", ["practice"])

    op.add_column(
        "service_agreements",
        sa.Column("template_kind", _KIND_REF, server_default="legal_services", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("service_agreements", "template_kind")
    op.drop_index("ix_legal_intakes_practice", table_name="legal_intakes")
    op.drop_column("legal_intakes", "category")
    op.drop_column("legal_intakes", "practice")
    _KIND.drop(op.get_bind(), checkfirst=True)
    _PRACTICE.drop(op.get_bind(), checkfirst=True)
