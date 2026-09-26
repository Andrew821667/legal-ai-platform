"""Пакеты услуг с сайта: выбранный пакет в обращении, заготовка под пакет.

Revision ID: 20260926_0046
Revises: 20260925_0045

Клиент выбирал на сайте «Экспресс-проверку договора — от 7 900 ₽», а до
юриста это доходило строкой в описании: договор он собирал заново руками.
Теперь пакет — поля обращения (снимок названия и цены на момент заказа), а
заготовка юриста может быть привязана к пакету: по такому обращению форма
договора заполняется ею сама.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260926_0046"
down_revision = "20260925_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("legal_intakes", sa.Column("package_id", sa.String(64), nullable=True))
    op.add_column("legal_intakes", sa.Column("package_title", sa.String(255), nullable=True))
    op.add_column("legal_intakes", sa.Column("package_price_text", sa.String(64), nullable=True))
    op.add_column("agreement_templates", sa.Column("package_id", sa.String(64), nullable=True))
    # Один пакет — одна заготовка: иначе форме пришлось бы гадать, какую взять.
    op.create_unique_constraint("uq_agreement_templates_package_id", "agreement_templates", ["package_id"])


def downgrade() -> None:
    op.drop_constraint("uq_agreement_templates_package_id", "agreement_templates", type_="unique")
    op.drop_column("agreement_templates", "package_id")
    op.drop_column("legal_intakes", "package_price_text")
    op.drop_column("legal_intakes", "package_title")
    op.drop_column("legal_intakes", "package_id")
