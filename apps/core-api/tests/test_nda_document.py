"""Соглашение о конфиденциальности и его версионирование.

Подпись — нажатие кнопки, поэтому ценность имеет не факт, а зафиксированные
обстоятельства: какой именно текст видел клиент и не изменился ли он потом.
"""

from __future__ import annotations

from core_api.nda_document import (
    NDA_TEXT,
    NDA_VERSION,
    document_hash,
    render_nda_text,
)


def test_hash_is_stable_for_the_same_text() -> None:
    """Одинаковый текст даёт одинаковую сумму — иначе проверка бессмысленна."""
    first = render_nda_text("ИП Иванов")
    second = render_nda_text("ИП Иванов")

    assert document_hash(first) == document_hash(second)


def test_hash_changes_when_text_changes() -> None:
    """Правка документа обязана менять сумму, иначе подмену не заметить."""
    assert document_hash(render_nda_text("ИП Иванов")) != document_hash(
        render_nda_text("ООО Ромашка")
    )


def test_document_declares_simple_electronic_signature() -> None:
    """Без явного признания ПЭП сторонами нажатие кнопки не является подписью.

    Это требование статьи 6 Федерального закона № 63-ФЗ: стороны должны
    заранее договориться считать такой способ подписанием.
    """
    text = render_nda_text("ИП Иванов")

    assert "простой электронной подписью" in text
    assert "63-ФЗ" in text


def test_document_records_what_is_fixed_on_signing() -> None:
    """Клиент должен видеть, что именно фиксируется при подписании."""
    text = render_nda_text("ИП Иванов")

    for expected in ("даты", "аккаунта", "контрольной суммы"):
        assert expected in text


def test_document_is_not_a_service_agreement() -> None:
    """Соглашение о конфиденциальности не должно читаться как договор услуг."""
    text = render_nda_text("ИП Иванов")

    # Переносы строк в документе не должны влиять на проверку смысла.
    flat = " ".join(text.split())
    assert "не является договором об оказании юридических услуг" in flat


def test_operator_name_is_substituted() -> None:
    text = render_nda_text("ИП Попов А.В.")

    assert "ИП Попов А.В." in text
    assert "{operator_name}" not in text


def test_missing_operator_name_does_not_break_document() -> None:
    text = render_nda_text("")

    assert "Исполнитель" in text
    assert "{operator_name}" not in text


def test_version_is_embedded_in_the_text() -> None:
    """Версия внутри текста: подпись привязана к конкретной редакции."""
    assert NDA_VERSION in render_nda_text("ИП Иванов")
    assert "{version}" in NDA_TEXT


def test_document_covers_deletion_on_request() -> None:
    """Клиент должен видеть, что может потребовать удаления материалов."""
    assert "удалить материалы" in render_nda_text("ИП Иванов")
