"""Журнал удалений — триггер в базе на таблицах с делами клиентов.

Revision ID: 20260925_0045
Revises: 20260925_0044

Обращение клиента исчезло из базы без записи в аудите — строку удалили мимо
кода приложения. Триггер ловит любое удаление и пишет, что и кем удалено,
без содержимого строки (см. core_api/deletion_log.py).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260925_0045"
down_revision = "20260925_0044"
branch_labels = None
depends_on = None

_TABLES = ("leads", "legal_intakes", "service_agreements", "work_acts", "nda_signatures", "intake_documents")


def upgrade() -> None:
    op.create_table(
        "deletion_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("table_name", sa.String(64), nullable=False),
        sa.Column("row_id", sa.String(64), nullable=True),
        sa.Column("lead_id", sa.String(64), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("db_user", sa.String(64), nullable=False, server_default=sa.text("session_user")),
        sa.Column(
            "application_name", sa.String(128), nullable=True,
            server_default=sa.text("current_setting('application_name', true)"),
        ),
        sa.Column("client_addr", sa.String(64), nullable=True, server_default=sa.text("inet_client_addr()::text")),
        sa.Column("txid", sa.BigInteger(), nullable=True, server_default=sa.text("txid_current()")),
    )
    op.create_index("ix_deletion_log_deleted_at", "deletion_log", ["deleted_at"])
    op.execute(
        """
        CREATE OR REPLACE FUNCTION log_deletion() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            old_row jsonb := to_jsonb(OLD);
        BEGIN
            INSERT INTO deletion_log (table_name, row_id, lead_id)
            VALUES (TG_TABLE_NAME, old_row->>'id', old_row->>'lead_id');
            RETURN OLD;
        END
        $$;
        """
    )
    for table in _TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_log_deletion ON {table}")
        op.execute(
            f"CREATE TRIGGER trg_log_deletion AFTER DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION log_deletion()"
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_log_deletion ON {table}")
    op.execute("DROP FUNCTION IF EXISTS log_deletion()")
    op.drop_index("ix_deletion_log_deleted_at", table_name="deletion_log")
    op.drop_table("deletion_log")
