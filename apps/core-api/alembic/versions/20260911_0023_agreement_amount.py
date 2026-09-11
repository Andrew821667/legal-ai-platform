"""Структурированная сумма договора рядом с текстом стоимости.

`price_text` остаётся: это формулировка, которая уходит в документ и которую
подписывает клиент («10 000 ₽, НДС не облагается»). Считать по ней нельзя —
один и тот же договор в двух редакциях называл сумму «10 тысяч» и
«10000 руб». `amount_minor` — сумма к учёту в копейках, по ней строятся итоги.

Бэкофилл нарочно осторожный: берёт только однозначные формы («10000 руб»,
«10 тысяч», «10 000 ₽»). Всё, где есть оговорки или диапазон, остаётся
пустым — юрист проставит сам, и это честнее, чем угадать.

Revision ID: 20260911_0023
Revises: 20260911_0022
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision = "20260911_0023"
down_revision = "20260911_0022"
branch_labels = None
depends_on = None

_MONEY = re.compile(
    r"^\s*(?P<int>\d{1,3}(?:[  ]\d{3})+|\d+)"
    r"(?:[.,](?P<frac>\d{2}))?"
    r"\s*(?P<thousands>тыс\.?|тысяч[аи]?|k)?"
    r"\s*(?:руб\.?|рублей|рубля|₽|р\.?)?"
    r"\s*$",
    re.IGNORECASE,
)


def parse_rubles_to_minor(text: str | None) -> int | None:
    """«10 тысяч» → 1_000_000 копеек; всё с оговорками → None."""
    if not text:
        return None
    match = _MONEY.match(text)
    if not match:
        return None
    whole = int(re.sub(r"[  ]", "", match.group("int")))
    if match.group("thousands"):
        whole *= 1000
    frac = int(match.group("frac") or 0)
    if whole == 0 and frac == 0:
        return None
    return whole * 100 + frac


def upgrade() -> None:
    op.add_column("service_agreements", sa.Column("amount_minor", sa.BigInteger(), nullable=True))
    op.add_column(
        "service_agreements",
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, price_text FROM service_agreements WHERE amount_minor IS NULL")
    ).all()
    for row_id, price_text in rows:
        minor = parse_rubles_to_minor(price_text)
        if minor is not None:
            bind.execute(
                sa.text("UPDATE service_agreements SET amount_minor = :minor WHERE id = :id"),
                {"minor": minor, "id": row_id},
            )


def downgrade() -> None:
    op.drop_column("service_agreements", "currency")
    op.drop_column("service_agreements", "amount_minor")
