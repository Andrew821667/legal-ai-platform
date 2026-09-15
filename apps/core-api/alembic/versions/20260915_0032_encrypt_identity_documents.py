"""Реквизиты документа подписанта — только зашифрованными.

Revision ID: 20260915_0032
Revises: 20260914_0031

До этой ревизии реквизиты паспорта лежали в базе открытым текстом — и в
её резервных копиях тоже. Столбцы расширяются под токен Fernet, а все уже
записанные строки дошифровываются тем же ключом, которым дальше работает
приложение. Без ключа миграция останавливается до того, как что-то тронет:
это лучше, чем выкатиться и оставить паспорта открытыми.
"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "20260915_0032"
down_revision = "20260914_0031"
branch_labels = None
depends_on = None

_TABLES = ("nda_personal_data_consents", "nda_signatures")


def _fernet():
    key = (os.getenv("PII_ENCRYPTION_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            "PII_ENCRYPTION_KEY is required for migration 20260915_0032: "
            "set it in the environment before upgrading"
        )
    from cryptography.fernet import Fernet

    return Fernet(key.encode("utf-8"))


def upgrade() -> None:
    from core_api.pii import _PREFIX, is_encrypted

    bind = op.get_bind()
    for table in _TABLES:
        op.alter_column(table, "signer_identity_document", type_=sa.Text(), existing_type=sa.String(500))

    pending = []
    for table in _TABLES:
        rows = bind.execute(
            sa.text(f"SELECT id, signer_identity_document FROM {table} WHERE signer_identity_document IS NOT NULL")
        ).all()
        pending.extend((table, row_id, value) for row_id, value in rows if not is_encrypted(value))
    if not pending:
        return

    fernet = _fernet()
    for table, row_id, value in pending:
        token = _PREFIX + fernet.encrypt(str(value).encode("utf-8")).decode("ascii")
        bind.execute(
            sa.text(f"UPDATE {table} SET signer_identity_document = :value WHERE id = :id"),
            {"value": token, "id": row_id},
        )


def downgrade() -> None:
    # Обратный путь оставляет данные зашифрованными, а не расшифровывает их
    # обратно в открытый текст: откат кода не повод раскрывать паспорта.
    # Сузить столбец нельзя — токен длиннее 500 символов, — поэтому Text
    # остаётся. Приложение до 0032 прочитает токен как непрозрачную строку.
    pass
