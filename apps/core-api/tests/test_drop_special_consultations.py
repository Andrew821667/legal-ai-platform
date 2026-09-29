"""Миграция 0050: таблицы «специальных консультаций» удаляются, откат их возвращает.

Схема в тестах создана ORM (моделей больше нет), поэтому ревизию вызываем
напрямую — тем же кодом, что пойдёт на прод.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from core_api.db import engine

_TABLES = ("special_consultation_products", "special_consultation_orders", "special_consultation_payments")


def _migration():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20260929_0050_drop_special_consultations.py"
    spec = importlib.util.spec_from_file_location("m0050", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _existing(conn) -> set[str]:
    rows = conn.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'special_consultation%'")
    )
    return {row[0] for row in rows}


def _types(conn) -> set[str]:
    rows = conn.execute(
        text(
            "SELECT typname FROM pg_type WHERE typname IN ('payment_provider_enum', 'payment_transaction_status_enum', "
            "'special_consultation_order_source_enum', 'special_consultation_order_status_enum')"
        )
    )
    return {row[0] for row in rows}


def test_downgrade_restores_and_upgrade_drops_tables_and_types() -> None:
    module = _migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()
        assert _existing(conn) == set(_TABLES)
        assert conn.execute(text("SELECT count(*) FROM special_consultation_products")).scalar_one() == 3
        assert len(_types(conn)) == 4

    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            module.upgrade()  # повторный запуск ничего не ломает
        assert _existing(conn) == set()
        assert _types(conn) == set()
