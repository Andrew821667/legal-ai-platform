"""Удаление таблиц «специальных консультаций».

API /api/v1/special-consultations убран в #454: платную консультацию продаёт
запись по времени (consultation_slots). Проверено на проде 2026-09-29: заказов 0,
платежей 0, в каталоге — только три стартовых продукта из миграции 0012.
Типы-перечисления этих таблиц нигде больше не используются.

Откат восстанавливает пустые таблицы с тем же каталогом — повторным запуском 0012.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import op

revision = "20260929_0050"
down_revision = "20260926_0049"
branch_labels = None
depends_on = None

_TABLES = ("special_consultation_payments", "special_consultation_orders", "special_consultation_products")
_TYPES = (
    "payment_transaction_status_enum",
    "payment_provider_enum",
    "special_consultation_order_status_enum",
    "special_consultation_order_source_enum",
)


def upgrade() -> None:
    # Платежи ссылаются на заказы, заказы — на каталог: удаляем в этом порядке.
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")
    for type_name in _TYPES:
        op.execute(f"DROP TYPE IF EXISTS {type_name}")


def downgrade() -> None:
    path = Path(__file__).with_name("20260312_0012_sp_consult.py")
    spec = importlib.util.spec_from_file_location("sp_consult_0012", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
