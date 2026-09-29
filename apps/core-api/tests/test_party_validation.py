"""Данные стороны проверяются по существу (shared/party_validation.py).

Закрепляется: абракадабра вместо паспорта, ФИО с цифрами, дата выдачи из
будущего, ИНН и ОГРН с неверной контрольной цифрой не проходят; настоящие
реквизиты проходят. Проверка — в ядре, её не обойти ни сайтом, ни ботом.
"""

from __future__ import annotations

from datetime import date

import pytest
from shared import party_validation as v

TODAY = date(2026, 9, 30)
PASSPORT = "4501 123456, выдан ОВД района Арбат г. Москвы, 01.02.2010, код подразделения 770-001"


@pytest.mark.parametrize(
    "value",
    [
        PASSPORT,
        "45 01 № 123456 выдан ГУ МВД России по г. Москве 05.06.2021 код 770-093",
        "Паспорт 4510 654321, выдан Отделением УФМС России по г. Москве по району Хамовники 12.03.2015, 770-045",
        "Паспорт иностранного гражданина AB1234567, выдан 15.03.2019",
        "Вид на жительство 82 № 1234567, выдан 10.10.2022",
    ],
)
def test_real_documents_pass(value) -> None:
    assert v.identity_document(value, today=TODAY) == value


@pytest.mark.parametrize(
    ("value", "hint"),
    [
        ("абракадабра", "серия и номер"),
        ("фывапролджэ йцукенгшщзх", "серия и номер"),
        ("4501 123456 выдан фывапр олдж 01.02.2010 770-001", "кем выдан"),
        ("4501 123456, выдан ОВД 01.02.2030, 770-001", "в будущем"),
        ("4501 123456 выдан УФМС 01.02.1995 770-001", "1 октября 1997"),
        ("4501 123456 выдан УФМС", "дату выдачи"),
        ("4501 123456 выдан УФМС 01.02.2010", "код подразделения"),
        ("0000 000000 ОВД 01.01.2010 770-001", "выглядят неверно"),
        ("4501 123456 ОВД 31.02.2010 770-001", "не существует"),
        ("Паспорт иностранного гражданина абв", "вид, номер и дату"),
    ],
)
def test_gibberish_documents_are_refused_with_a_hint(value, hint) -> None:
    with pytest.raises(v.PartyDataError, match=hint):
        v.identity_document(value, today=TODAY)


def test_names() -> None:
    for name in ("Иванов Иван Иванович", "Анна-Мария Петрова", "Мкртчян Ашот", "O'Neil John"):
        assert v.full_name(f"  {name} ") == name
    for bad in ("абракадабра", "Иван 123", "ффф ввв", "Ivanov Иван", "Иванов И", "вфрдл кнгш"):
        with pytest.raises(v.PartyDataError):
            v.full_name(bad)


def test_contacts() -> None:
    for good in ("+7 900 123-45-67", "89001234567", "anna@yandex.ru", "@anna_tg", "+44 20 7946 0958"):
        assert v.contact(good) == good
    for bad in ("12345", "79999999999", "абв", "anna@", "@ab"):
        with pytest.raises(v.PartyDataError):
            v.contact(bad)


def test_addresses() -> None:
    assert v.address("г. Москва, ул. Тверская, д. 1") == "г. Москва, ул. Тверская, д. 1"
    for bad in ("абракадабра", "Москва", "12345678901", "ввв ррр 1"):
        with pytest.raises(v.PartyDataError):
            v.address(bad)


def test_inn_and_ogrn_checksums() -> None:
    assert v.inn("7707083893") == "7707083893"  # Сбербанк
    assert v.inn("500100732259") == "500100732259"
    assert v.ogrn("1027700132195", inn_value="7707083893") == "1027700132195"
    assert v.ogrn("304500116000157", inn_value="500100732259") == "304500116000157"
    for bad in ("7707083894", "770708389", "abcdefghij"):
        with pytest.raises(v.PartyDataError):
            v.inn(bad)
    with pytest.raises(v.PartyDataError, match="контрольная"):
        v.ogrn("1027700132196")
    with pytest.raises(v.PartyDataError, match="разных видов"):
        v.ogrn("304500116000157", inn_value="7707083893")


def test_organization_fields() -> None:
    assert v.org_name("ООО «Ромашка»") == "ООО «Ромашка»"
    assert v.position("генеральный директор") == "генеральный директор"
    assert v.authority_basis("Устав") == "Устав"
    for fn in (v.org_name, v.position, v.authority_basis):
        with pytest.raises(v.PartyDataError):
            fn("123")
