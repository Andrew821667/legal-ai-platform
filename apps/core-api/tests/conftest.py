from __future__ import annotations

import os

import pytest

from core_api.db import Base, engine


# Реквизиты документа подписанта пишутся только зашифрованными; без ключа
# запись падает намеренно. Тестам нужен свой, фиктивный ключ.
os.environ.setdefault("PII_ENCRYPTION_KEY", "t8W5A2jJ0kK1h3Qn0m7wq1y5F2rC4b9Zp6x8VdL0sYo=")


@pytest.fixture(scope="session", autouse=True)
def ensure_core_api_test_schema() -> None:
    Base.metadata.create_all(bind=engine, checkfirst=True)
