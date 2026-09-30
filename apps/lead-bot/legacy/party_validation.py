"""Проверка данных стороны: ФИО, контакт, паспорт, адрес, ИНН, ОГРН.

Эти данные попадают в NDA, согласие на обработку ПД и договор — документ с
абракадаброй вместо паспорта юридически ничего не стоит. Проверка одна и та
же в ядре (последнее слово, через него идут и сайт, и бот) и в боте (подсказка
сразу, без похода в ядро): файл копируется в бот как есть
(apps/lead-bot/legacy/party_validation.py), тест сверяет копии.

Каждая функция возвращает нормализованное значение или бросает
PartyDataError с текстом для человека — по-русски, с примером.
Смысл имени проверить нельзя; отсекаем то, что заведомо не имя, не паспорт и
не адрес: цифры в ФИО, слова без гласных, «ааааа», паспорт без серии и номера,
дату выдачи из будущего, ИНН с неверной контрольной суммой.
"""

from __future__ import annotations

import re
from datetime import date

__all__ = [
    "PartyDataError",
    "address",
    "authority_basis",
    "contact",
    "full_name",
    "identity_document",
    "inn",
    "ogrn",
    "org_name",
    "position",
]


class PartyDataError(ValueError):
    """Данные не прошли проверку; текст — для человека."""


_VOWELS = set("аеёиоуыэюяaeiouy")
_CYR_WORD = re.compile(r"^[А-ЯЁа-яё]+(?:[-'’][А-ЯЁа-яё]+)*$")
_LAT_WORD = re.compile(r"^[A-Za-z]+(?:[-'’][A-Za-z]+)*$")
_LETTERS = re.compile(r"[А-ЯЁа-яёA-Za-z]+")
_TRIPLE = re.compile(r"(.)\1\1")

NAME_EXAMPLE = "Например: Иванов Иван Иванович."
PASSPORT_EXAMPLE = "Например: 4501 123456, выдан ОВД района Арбат г. Москвы, 01.02.2010, код подразделения 770-001."
# Паспорт гражданина РФ нового образца выдают с 1 октября 1997 года.
RF_PASSPORT_SINCE = date(1997, 10, 1)


def _squash(value: str | None) -> str:
    return " ".join((value or "").split())


def _looks_like_word(letters: str) -> bool:
    """Слово, а не набор букв: есть гласная и нет трёх одинаковых подряд."""
    lowered = letters.lower()
    return any(ch in _VOWELS for ch in lowered) and not _TRIPLE.search(lowered)


def _is_abbreviation(token: str) -> bool:
    """ОВД, МВД, УФМС, ГУВД — заглавные сокращения без гласных допустимы."""
    return 2 <= len(token) <= 6 and token.isupper()


def full_name(value: str | None) -> str:
    """Фамилия и имя (и отчество): 2–5 слов из букв, без цифр и мусора."""
    text = _squash(value)
    words = text.split(" ") if text else []
    if not 2 <= len(words) <= 5:
        raise PartyDataError(f"Укажите фамилию и имя полностью, и отчество, если есть. {NAME_EXAMPLE}")
    scripts = set()
    for word in words:
        if _CYR_WORD.match(word):
            scripts.add("cyr")
        elif _LAT_WORD.match(word):
            scripts.add("lat")
        else:
            raise PartyDataError(f"В ФИО могут быть только буквы и дефис — без цифр и знаков. {NAME_EXAMPLE}")
        letters = re.sub(r"[-'’]", "", word)
        if len(letters) < 2 or not _looks_like_word(letters):
            raise PartyDataError(f"«{word}» не похоже на имя или фамилию. {NAME_EXAMPLE}")
    if len(scripts) > 1:
        raise PartyDataError(f"Напишите ФИО одним алфавитом — русскими или латинскими буквами. {NAME_EXAMPLE}")
    return text


_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-zА-Яа-яЁё]{2,}$")
_USERNAME = re.compile(r"^@[A-Za-z][A-Za-z0-9_]{4,31}$")
_PHONE_CHARS = re.compile(r"^\+?[\d\s()\-.]+$")


def _phone_ok(text: str) -> bool:
    if not _PHONE_CHARS.match(text):
        return False
    digits = re.sub(r"\D", "", text)
    if len(set(digits)) < 3:  # 7999999999 — не номер
        return False
    if len(digits) == 11 and digits[0] in "78":
        return digits[1] in "3489"
    if len(digits) == 10:
        return digits[0] in "3489"
    return text.startswith("+") and 11 <= len(digits) <= 15


def contact(value: str | None) -> str:
    """Телефон, почта или ник в Telegram."""
    text = _squash(value)
    if _EMAIL.match(text) or _USERNAME.match(text) or _phone_ok(text):
        return text
    raise PartyDataError(
        "Укажите телефон (например, +7 900 123-45-67), почту (имя@почта.ру) или ник в Telegram (@username)."
    )


_RF_NUMBER = re.compile(r"(?<![\d-])(\d{2})\s?(\d{2})\s*(?:№|N|No\.?)?\s*(\d{6})(?![\d-])", re.IGNORECASE)
_DATE = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)")
_DATE_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_DIVISION = re.compile(r"(?<!\d)(\d{3})-(\d{3})(?!\d)")
_FOREIGN = re.compile(
    r"иностран|загран|вид\w* на жительств|\bвнж\b|passport|разрешени\w* на временн|\bрвп\b|удостоверени|беженц",
    re.IGNORECASE,
)
# Кем выдан паспорт РФ: ОВД, УВД, ГУ МВД, УФМС, ТП УФМС, отдел полиции, паспортный
# стол, МФЦ. Название органа — самый надёжный признак настоящих реквизитов.
_ISSUER = re.compile(
    r"овд|увд|мвд|фмс|отдел|управлени|милици|полици|паспортн|миграц|консульств|посольств|мфц|(?<![а-яё])(?:тп|оп|ом)(?![а-яё])",
    re.IGNORECASE,
)


def _dates(text: str) -> list[date]:
    """Даты вида 01.02.2010 и 2010-02-01 (так пишут в иностранных документах)."""
    found = []
    matches = [(m, m.groups()) for m in _DATE.finditer(text)]
    matches += [(m, tuple(reversed(m.groups()))) for m in _DATE_ISO.finditer(text)]
    for match, (day, month, year) in matches:
        try:
            found.append(date(int(year), int(month), int(day)))
        except ValueError:
            raise PartyDataError(f"Дата «{match.group(0)}» не существует — проверьте день и месяц.") from None
    return found


def identity_document(value: str | None, *, today: date | None = None) -> str:
    """Паспорт РФ (серия и номер, кем и когда выдан, код подразделения) или иной документ."""
    text = _squash(value)
    today = today or date.today()
    dates = _dates(text)
    if any(d > today for d in dates):
        raise PartyDataError("Дата выдачи не может быть в будущем — проверьте её.")

    if _FOREIGN.search(text):
        numbers = [t for t in re.findall(r"[A-Za-zА-Яа-я0-9№-]{6,}", text) if sum(ch.isdigit() for ch in t) >= 5]
        if not numbers or not dates:
            raise PartyDataError(
                "Для иностранного документа укажите его вид, номер и дату выдачи. "
                "Например: Паспорт иностранного гражданина AB1234567, выдан 15.03.2019."
            )
        return text

    match = _RF_NUMBER.search(text)
    if not match:
        raise PartyDataError(
            "Не похоже на паспорт: нужны серия и номер (10 цифр), кем выдан, дата выдачи и код подразделения. "
            f"{PASSPORT_EXAMPLE} Для иностранного документа начните с его вида: «Паспорт иностранного "
            "гражданина …», «Вид на жительство …»."
        )
    digits = "".join(match.groups())
    if digits[:2] == "00" or len(set(digits)) < 3:
        raise PartyDataError(f"Серия и номер паспорта выглядят неверно — проверьте их. {PASSPORT_EXAMPLE}")
    if not dates:
        raise PartyDataError(f"Укажите дату выдачи паспорта. {PASSPORT_EXAMPLE}")
    if not any(d >= RF_PASSPORT_SINCE for d in dates):
        raise PartyDataError("Паспорта РФ выдают с 1 октября 1997 года — проверьте дату выдачи.")
    if not _DIVISION.search(text):
        raise PartyDataError(f"Укажите код подразделения — шесть цифр через дефис, он есть в паспорте. {PASSPORT_EXAMPLE}")
    if not _ISSUER.search(text):
        raise PartyDataError(
            f"Укажите, кем выдан паспорт, — как в самом паспорте (ОВД, УФМС, ГУ МВД, отдел полиции…). {PASSPORT_EXAMPLE}"
        )
    return text


def address(value: str | None) -> str:
    """Адрес с населённым пунктом, улицей и номером дома."""
    text = _squash(value)
    words = [w for w in _LETTERS.findall(text) if len(w) >= 2]
    if (
        len(text) < 10
        or len(words) < 2
        or not re.search(r"\d", text)
        or not any(len(w) >= 3 and _looks_like_word(w) for w in words)
    ):
        raise PartyDataError("Укажите адрес полностью: город, улицу, дом. Например: г. Москва, ул. Тверская, д. 1, кв. 5.")
    return text


def _text_field(value: str | None, *, min_letters: int, message: str) -> str:
    text = _squash(value)
    letters = "".join(_LETTERS.findall(text))
    words = [w for w in _LETTERS.findall(text) if len(w) >= 3]
    if len(letters) < min_letters or not any(_looks_like_word(w) or _is_abbreviation(w) for w in words):
        raise PartyDataError(message)
    return text


def org_name(value: str | None) -> str:
    return _text_field(value, min_letters=3, message="Укажите название организации, например: ООО «Ромашка».")


def position(value: str | None) -> str:
    return _text_field(value, min_letters=4, message="Укажите должность подписанта, например: генеральный директор.")


def authority_basis(value: str | None) -> str:
    return _text_field(
        value, min_letters=5, message="Укажите, на чём основаны полномочия: «Устав» или «Доверенность № 12 от 01.02.2026»."
    )


def _checksum(digits: str, weights: tuple[int, ...]) -> int:
    return sum(int(d) * w for d, w in zip(digits, weights, strict=False)) % 11 % 10


def inn(value: str | None) -> str:
    """ИНН организации (10 цифр) или ИП (12 цифр) с верной контрольной суммой."""
    digits = re.sub(r"\s", "", value or "")
    if not digits.isdigit() or len(digits) not in (10, 12):
        raise PartyDataError("ИНН — 10 цифр у организации или 12 у ИП.")
    if len(digits) == 10:
        ok = _checksum(digits, (2, 4, 10, 3, 5, 9, 4, 6, 8)) == int(digits[9])
    else:
        ok = _checksum(digits, (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)) == int(digits[10]) and _checksum(
            digits, (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        ) == int(digits[11])
    if not ok:
        raise PartyDataError("В ИНН ошибка: контрольная цифра не сходится. Проверьте номер.")
    return digits


def ogrn(value: str | None, *, inn_value: str | None = None) -> str:
    """ОГРН (13 цифр) или ОГРНИП (15 цифр) с верной контрольной цифрой; вид — под стать ИНН."""
    digits = re.sub(r"\s", "", value or "")
    if not digits.isdigit() or len(digits) not in (13, 15):
        raise PartyDataError("ОГРН — 13 цифр у организации, ОГРНИП — 15 цифр у ИП.")
    control = int(digits[:-1]) % (11 if len(digits) == 13 else 13) % 10
    if control != int(digits[-1]):
        raise PartyDataError("В ОГРН ошибка: контрольная цифра не сходится. Проверьте номер.")
    if inn_value and {len(inn_value), len(digits)} not in ({10, 13}, {12, 15}):
        raise PartyDataError("ИНН и ОГРН от разных видов лица: у организации ИНН 10 и ОГРН 13 цифр, у ИП — 12 и 15.")
    return digits
