"""Запись на платную консультацию: время юриста и бронь клиента.

Revision ID: 20260926_0049
Revises: 20260926_0048

Юрист открывает время, клиент выбирает его на сайте, оплачивает по QR и
сообщает об оплате, юрист подтверждает поступление. Бронь — строка того же
слота (см. core_api/consultations.py).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260926_0049"
down_revision = "20260926_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consultation_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("status", sa.String(16), nullable=False, server_default="free"),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "intake_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("legal_intakes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("price_minor", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(16), nullable=True),
        sa.Column("access_token", sa.String(64), nullable=True, unique=True),
        sa.Column("held_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receipt_ref", sa.String(500), nullable=True),
        sa.Column("receipt_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Одно время — один живой слот: второй на то же время юрист открыть не может.
    op.create_index(
        "uq_consultation_slots_live_start",
        "consultation_slots",
        ["starts_at"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled'"),
    )
    op.create_index("ix_consultation_slots_status", "consultation_slots", ["status", "starts_at"])


def downgrade() -> None:
    op.drop_index("ix_consultation_slots_status", table_name="consultation_slots")
    op.drop_index("uq_consultation_slots_live_start", table_name="consultation_slots")
    op.drop_table("consultation_slots")
