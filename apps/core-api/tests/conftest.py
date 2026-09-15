from __future__ import annotations

import os

import pytest
from sqlalchemy import select

from core_api.db import Base, SessionLocal, engine
from core_api.models import SpecialConsultationProduct


def _seed_special_consultation_products() -> None:
    rows = [
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
    ]

    db = SessionLocal()
    try:
        existing_codes = set(db.execute(select(SpecialConsultationProduct.code)).scalars().all())
        for row in rows:
            if row["code"] in existing_codes:
                continue
            db.add(SpecialConsultationProduct(**row))
        db.commit()
    finally:
        db.close()


# Реквизиты документа подписанта пишутся только зашифрованными; без ключа
# запись падает намеренно. Тестам нужен свой, фиктивный ключ.
os.environ.setdefault("PII_ENCRYPTION_KEY", "t8W5A2jJ0kK1h3Qn0m7wq1y5F2rC4b9Zp6x8VdL0sYo=")


@pytest.fixture(scope="session", autouse=True)
def ensure_core_api_test_schema() -> None:
    Base.metadata.create_all(bind=engine, checkfirst=True)
    _seed_special_consultation_products()
