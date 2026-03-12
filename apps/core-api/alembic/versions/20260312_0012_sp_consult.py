"""Add special consultation products, orders, and payments.

Revision ID: 20260312_0012_sp_consult
Revises: 20260307_0011_reader_rollup
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260312_0012_sp_consult"
down_revision = "20260307_0011_reader_rollup"
branch_labels = None
depends_on = None


special_consultation_order_source_enum = postgresql.ENUM(
    "lead_bot",
    "web",
    "admin",
    name="special_consultation_order_source_enum",
    create_type=False,
)
special_consultation_order_status_enum = postgresql.ENUM(
    "requested",
    "awaiting_quote",
    "awaiting_payment",
    "paid",
    "fulfilled",
    "cancelled",
    "refunded",
    name="special_consultation_order_status_enum",
    create_type=False,
)
payment_provider_enum = postgresql.ENUM(
    "manual",
    "yookassa",
    "telegram",
    name="payment_provider_enum",
    create_type=False,
)
payment_transaction_status_enum = postgresql.ENUM(
    "created",
    "pending",
    "requires_action",
    "paid",
    "failed",
    "cancelled",
    "refunded",
    name="payment_transaction_status_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    special_consultation_order_source_enum.create(bind, checkfirst=True)
    special_consultation_order_status_enum.create(bind, checkfirst=True)
    payment_provider_enum.create(bind, checkfirst=True)
    payment_transaction_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "special_consultation_products",
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'RUB'"), nullable=False),
        sa.Column("base_price_minor", sa.Integer(), nullable=True),
        sa.Column("requires_manual_quote", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("highlights", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("fulfillment_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(
        "ix_special_consultation_products_active_sort",
        "special_consultation_products",
        ["is_active", "sort_order"],
        unique=False,
    )

    op.create_table(
        "special_consultation_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_code", sa.String(length=120), nullable=False),
        sa.Column("source", special_consultation_order_source_enum, nullable=False),
        sa.Column(
            "status",
            special_consultation_order_status_enum,
            server_default=sa.text("'requested'"),
            nullable=False,
        ),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("customer_name", sa.Text(), nullable=True),
        sa.Column("customer_contact", sa.Text(), nullable=True),
        sa.Column("customer_email", sa.Text(), nullable=True),
        sa.Column("customer_phone", sa.Text(), nullable=True),
        sa.Column("customer_company", sa.Text(), nullable=True),
        sa.Column("request_note", sa.Text(), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'RUB'"), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=True),
        sa.Column("payment_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["product_code"], ["special_consultation_products.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_special_consultation_orders_created", "special_consultation_orders", ["created_at"], unique=False)
    op.create_index(
        "ix_special_consultation_orders_status_created",
        "special_consultation_orders",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_special_consultation_orders_lead",
        "special_consultation_orders",
        ["lead_id"],
        unique=False,
        postgresql_where=sa.text("lead_id IS NOT NULL"),
    )
    op.create_index(
        "ix_special_consultation_orders_telegram_user_id",
        "special_consultation_orders",
        ["telegram_user_id"],
        unique=False,
        postgresql_where=sa.text("telegram_user_id IS NOT NULL"),
    )

    op.create_table(
        "special_consultation_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", payment_provider_enum, nullable=False),
        sa.Column(
            "status",
            payment_transaction_status_enum,
            server_default=sa.text("'created'"),
            nullable=False,
        ),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'RUB'"), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("confirmation_url", sa.Text(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["special_consultation_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_special_consultation_payments_order_created",
        "special_consultation_payments",
        ["order_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_special_consultation_payments_status_created",
        "special_consultation_payments",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ux_special_consultation_payments_provider_payment_id",
        "special_consultation_payments",
        ["provider", "provider_payment_id"],
        unique=True,
        postgresql_where=sa.text("provider_payment_id IS NOT NULL"),
    )
    op.create_index(
        "ux_special_consultation_payments_external_reference",
        "special_consultation_payments",
        ["external_reference"],
        unique=True,
        postgresql_where=sa.text("external_reference IS NOT NULL"),
    )

    products = sa.table(
        "special_consultation_products",
        sa.column("code", sa.String),
        sa.column("name", sa.Text),
        sa.column("description", sa.Text),
        sa.column("currency", sa.String),
        sa.column("base_price_minor", sa.Integer),
        sa.column("requires_manual_quote", sa.Boolean),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
        sa.column("highlights", postgresql.JSONB),
        sa.column("fulfillment_note", sa.Text),
    )
    op.bulk_insert(
        products,
        [
            {
                "code": "urgent_consultation",
                "name": "Срочная экспертная консультация",
                "description": "Приоритетный формат, когда нужен быстрый слот и фокус на срочном вопросе.",
                "currency": "RUB",
                "base_price_minor": None,
                "requires_manual_quote": True,
                "is_active": True,
                "sort_order": 10,
                "highlights": ["Приоритетный разбор", "Согласование формата вручную"],
                "fulfillment_note": "Стоимость и срок подтверждаются после короткого уточнения задачи.",
            },
            {
                "code": "document_review_consultation",
                "name": "Консультация с предварительным разбором документов",
                "description": "Формат для кейсов, где перед созвоном нужно посмотреть договор или пакет материалов.",
                "currency": "RUB",
                "base_price_minor": None,
                "requires_manual_quote": True,
                "is_active": True,
                "sort_order": 20,
                "highlights": ["Предварительный разбор документов", "Подходит для сложных кейсов"],
                "fulfillment_note": "Стоимость зависит от объема материалов и глубины разбора.",
            },
            {
                "code": "written_memo",
                "name": "Письменное заключение / expert memo",
                "description": "Отдельный письменный результат по итогам разбора вопроса или документов.",
                "currency": "RUB",
                "base_price_minor": None,
                "requires_manual_quote": True,
                "is_active": True,
                "sort_order": 30,
                "highlights": ["Письменная фиксация позиции", "Можно привязать к консультации"],
                "fulfillment_note": "Срок и цена зависят от объема вопроса и ожидаемого результата.",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ux_special_consultation_payments_external_reference", table_name="special_consultation_payments")
    op.drop_index("ux_special_consultation_payments_provider_payment_id", table_name="special_consultation_payments")
    op.drop_index("ix_special_consultation_payments_status_created", table_name="special_consultation_payments")
    op.drop_index("ix_special_consultation_payments_order_created", table_name="special_consultation_payments")
    op.drop_table("special_consultation_payments")

    op.drop_index("ix_special_consultation_orders_telegram_user_id", table_name="special_consultation_orders")
    op.drop_index("ix_special_consultation_orders_lead", table_name="special_consultation_orders")
    op.drop_index("ix_special_consultation_orders_status_created", table_name="special_consultation_orders")
    op.drop_index("ix_special_consultation_orders_created", table_name="special_consultation_orders")
    op.drop_table("special_consultation_orders")

    op.drop_index("ix_special_consultation_products_active_sort", table_name="special_consultation_products")
    op.drop_table("special_consultation_products")

    bind = op.get_bind()
    payment_transaction_status_enum.drop(bind, checkfirst=True)
    payment_provider_enum.drop(bind, checkfirst=True)
    special_consultation_order_status_enum.drop(bind, checkfirst=True)
    special_consultation_order_source_enum.drop(bind, checkfirst=True)
