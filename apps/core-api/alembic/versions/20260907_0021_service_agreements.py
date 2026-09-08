"""Двустороннее подписание договоров юридических услуг.

Revision ID: 20260907_0021
Revises: 20260905_0020
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

revision = "20260907_0021"
down_revision = "20260905_0020"
branch_labels = None
depends_on = None

_STATUS_NAME = "service_agreement_status_enum"
_STATUS_VALUES = (
    "draft",
    "sent",
    "viewed",
    "signed",
    "declined",
    "expired",
    "superseded",
    "cancelled",
)
_ROLE_NAME = "service_agreement_message_role_enum"
_ROLE_VALUES = ("client", "lawyer")

_STATUS = sa.Enum(*_STATUS_VALUES, name=_STATUS_NAME)
_STATUS_REF = ENUM(*_STATUS_VALUES, name=_STATUS_NAME, create_type=False)
_ROLE = sa.Enum(*_ROLE_VALUES, name=_ROLE_NAME)
_ROLE_REF = ENUM(*_ROLE_VALUES, name=_ROLE_NAME, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    _STATUS.create(bind, checkfirst=True)
    _ROLE.create(bind, checkfirst=True)

    op.add_column("nda_signatures", sa.Column("document_text", sa.Text(), nullable=True))

    op.create_table(
        "service_agreements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agreement_number", sa.String(64), nullable=False, unique=True),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="SET NULL")),
        sa.Column(
            "intake_id", UUID(as_uuid=True), sa.ForeignKey("legal_intakes.id", ondelete="SET NULL")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status", _STATUS_REF, server_default="draft", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "supersedes_id",
            UUID(as_uuid=True),
            sa.ForeignKey("service_agreements.id", ondelete="SET NULL"),
        ),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("scope_text", sa.Text(), nullable=False),
        sa.Column("exclusions_text", sa.Text(), nullable=False),
        sa.Column("schedule_text", sa.Text(), nullable=False),
        sa.Column("price_text", sa.String(500), nullable=False),
        sa.Column("payment_terms", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("prepared_by_telegram_user_id", sa.BigInteger()),
        sa.Column("operator_snapshot", JSONB(), nullable=False),
        sa.Column("client_snapshot", JSONB(), nullable=False),
        sa.Column("document_text", sa.Text(), nullable=False),
        sa.Column("document_version", sa.String(32), nullable=False),
        sa.Column("document_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("viewed_at", sa.DateTime(timezone=True)),
        sa.Column("signed_at", sa.DateTime(timezone=True)),
        sa.Column("declined_at", sa.DateTime(timezone=True)),
        sa.Column("client_telegram_user_id", sa.BigInteger()),
        sa.Column("signer_telegram_user_id", sa.BigInteger()),
        sa.Column("signer_telegram_username", sa.String(255)),
        sa.Column("signer_full_name", sa.String(255)),
        sa.Column("signer_contact", sa.String(255)),
        sa.Column("signer_org", sa.String(500)),
        sa.Column("signer_position", sa.String(255)),
        sa.Column("authority_basis", sa.String(500)),
        sa.Column("sent_chat_id", sa.BigInteger()),
        sa.Column("sent_message_id", sa.BigInteger()),
        sa.Column("sent_by_telegram_user_id", sa.BigInteger()),
        sa.Column("sent_callback_id", sa.String(255)),
        sa.Column("viewed_message_id", sa.BigInteger()),
        sa.Column("viewed_callback_id", sa.String(255)),
        sa.Column("signed_callback_id", sa.String(255)),
        sa.Column("declined_callback_id", sa.String(255)),
        sa.Column("decline_reason", sa.String(1000)),
    )
    op.create_index("ix_service_agreements_lead", "service_agreements", ["lead_id", "created_at"])
    op.create_index(
        "ix_service_agreements_intake", "service_agreements", ["intake_id", "created_at"]
    )
    op.create_index(
        "ix_service_agreements_client_tg",
        "service_agreements",
        ["client_telegram_user_id", "created_at"],
    )
    op.create_index("ix_service_agreements_status", "service_agreements", ["status", "created_at"])

    op.create_table(
        "service_agreement_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agreement_id",
            UUID(as_uuid=True),
            sa.ForeignKey("service_agreements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("role", _ROLE_REF, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger()),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_service_agreement_messages_agreement",
        "service_agreement_messages",
        ["agreement_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_service_agreement_messages_agreement", table_name="service_agreement_messages"
    )
    op.drop_table("service_agreement_messages")
    op.drop_index("ix_service_agreements_status", table_name="service_agreements")
    op.drop_index("ix_service_agreements_client_tg", table_name="service_agreements")
    op.drop_index("ix_service_agreements_intake", table_name="service_agreements")
    op.drop_index("ix_service_agreements_lead", table_name="service_agreements")
    op.drop_table("service_agreements")
    op.drop_column("nda_signatures", "document_text")
    _ROLE.drop(op.get_bind(), checkfirst=True)
    _STATUS.drop(op.get_bind(), checkfirst=True)
