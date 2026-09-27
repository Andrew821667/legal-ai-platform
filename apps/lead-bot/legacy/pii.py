"""Обезличивание текста перед отправкой в языковую модель.

Модели (OpenAI, DeepSeek) работают за рубежом. Персональные данные туда не
передаём: перед вызовом имена, контакты, номера документов, счетов и карт,
адреса и даты рождения заменяются метками вида [ИМЯ_1], а в ответе модели
метки возвращаются обратно. Модель видит суть обращения, юрист и клиент —
нормальный текст.

Замена обратимая только внутри одного вызова: таблица меток живёт в объекте
Masker и никуда не отправляется. Одинаковое значение внутри вызова получает
одну и ту же метку, чтобы модель понимала, что речь об одном человеке.

Это лучшая попытка, а не гарантия: необычное имя без отчества и без
контекста («зовут», «гражданин», известное имя собеседника) может пройти.
Поэтому известные имена собеседника передаются явно (known_names).

Модуль без зависимостей и одинаковый в двух местах: packages/shared (ядро) и
apps/lead-bot/legacy/pii.py (у бота свой образ). Совпадение копий проверяет
тест бота.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MASK_NOTE = (
    "Персональные данные в тексте заменены метками вида [ИМЯ_1], [ТЕЛЕФОН_1], [АДРЕС_1]. "
    "Используй метки как есть, не пытайся угадать и не проси реальные данные."
)

_PLACEHOLDER_RE = re.compile(r"\[?\b(ИМЯ|ТЕЛЕФОН|EMAIL|TELEGRAM|АДРЕС|ДОКУМЕНТ|СЧЁТ|КАРТА|ДАТА_РОЖДЕНИЯ)_(\d+)\b\]?")

_CAP = r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?"
_PATRONYMIC = r"[А-ЯЁ][а-яё]+(?:вич|вна|ична|инична|ич)(?:а|у|ем|е|ы|ой|ою)?"
_INITIALS = r"[А-ЯЁ]\.\s?[А-ЯЁ]\.?"
# Фамилии на -ов/-ев/-ин и их падежи. На -ский/-цкий — только в связке с
# именем или инициалами: иначе под правило попадают «Московский», «Российский».
_SURNAME = r"[А-ЯЁ][а-яё]+(?:ов|ев|ёв|ин|ын)(?:а|у|ым|ой|ою|е|ы|ых|ыми|им)?"
_SURNAME_ANY = rf"(?:{_SURNAME}|[А-ЯЁ][а-яё]+(?:ск|цк)(?:ий|ого|ому|им|ом|ая|ой|ую|ие|их)|{_CAP})"
# Слова с «фамильным» окончанием, которые фамилией не являются: города,
# ведомства и частые существительные в начале предложения («Магазин отказался…»).
_NOT_SURNAME_STEMS = (
    "ростов", "саратов", "псков", "тамбов", "королёв", "королев", "берлин", "минфин", "пушкин", "кремлин",
    "сахалин", "магазин", "бензин", "карантин", "витамин", "керосин", "остров", "покров",
)

_FIRST_NAMES = """
александр алексей анатолий андрей антон аркадий арсений артём артем борис вадим валентин валерий василий
виктор виталий владимир владислав всеволод вячеслав геннадий георгий герман глеб григорий давид даниил
денис дмитрий евгений егор иван игорь илья кирилл константин лев леонид максим марк михаил никита николай
олег павел пётр петр роман руслан святослав семён семен сергей станислав степан тимофей тимур фёдор федор
филипп эдуард юрий яков ярослав
александра алина алла анастасия ангелина анна антонина валентина валерия вера вероника виктория галина
дарья диана ева евгения екатерина елена елизавета жанна зинаида зоя инна ирина карина кира ксения лариса
лидия любовь людмила маргарита марина мария надежда наталья наталия нина оксана ольга полина раиса
светлана софия софья тамара татьяна ульяна юлия яна
""".split()


def _name_forms(name: str) -> str:
    """Регулярное выражение для имени во всех падежах: Иван/Ивана/Иваном, Ольга/Ольги/Ольгой."""
    lower = name.lower()
    stem = lower[:-1] if lower[-1] in "аяйьоеы" else lower
    endings = "а|я|у|ю|ом|ем|ём|ой|ей|ою|ею|е|и|ы|й|ь"
    return rf"{re.escape(stem)}(?:{endings})?"


_FIRST_NAME_FORMS = "|".join(_name_forms(name) for name in sorted(set(_FIRST_NAMES), key=len, reverse=True))


@dataclass
class Masker:
    """Одна замена на один вызов модели: mask() перед отправкой, restore() на ответ."""

    known_names: tuple[str, ...] = ()
    mapping: dict[str, str] = field(default_factory=dict)
    _placeholders: dict[tuple[str, str], str] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    def _placeholder(self, kind: str, value: str) -> str:
        key = (kind, value.strip().lower())
        found = self._placeholders.get(key)
        if found:
            return found
        self._counters[kind] = self._counters.get(kind, 0) + 1
        placeholder = f"[{kind}_{self._counters[kind]}]"
        self._placeholders[key] = placeholder
        self.mapping[placeholder] = value.strip()
        return placeholder

    def _sub(self, pattern: str | re.Pattern[str], kind: str, text: str, *, group: int = 0, flags: int = 0) -> str:
        compiled = pattern if isinstance(pattern, re.Pattern) else re.compile(pattern, flags)

        def replace(match: re.Match[str]) -> str:
            value = match.group(group)
            if not value or not value.strip():
                return match.group(0)
            whole = match.group(0)
            start = match.start(group) - match.start(0)
            return whole[:start] + self._placeholder(kind, value) + whole[start + len(value):]

        return compiled.sub(replace, text)

    def mask(self, text: str) -> str:
        if not text:
            return text
        text = self._sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "EMAIL", text)
        text = self._sub(r"(?:https?://)?t\.me/[A-Za-z0-9_]{4,}", "TELEGRAM", text)
        text = self._sub(r"(?<![\w@.])@[A-Za-z][A-Za-z0-9_]{3,31}\b", "TELEGRAM", text)
        text = self._cards(text)
        text = self._sub(r"(?<!\d)\d{20}(?!\d)", "СЧЁТ", text)
        text = self._sub(r"(?<!\d)\d{3}-\d{3}-\d{3}[ -]\d{2}(?!\d)", "ДОКУМЕНТ", text)
        text = self._sub(
            r"(?i)\b(?:инн|огрнип|огрн|снилс|паспорт\w*|серия(?:\s+и\s+номер)?|номер\s+паспорта)\s*[:№]?\s*((?:\d[\s-]?){6,14}\d)",
            "ДОКУМЕНТ",
            text,
            group=1,
        )
        text = self._sub(r"(?<!\d)\d{2}\s?\d{2}\s?№?\s?\d{6}(?!\d)", "ДОКУМЕНТ", text)
        text = self._sub(r"(?<!\d)\d{12}(?!\d)", "ДОКУМЕНТ", text)
        text = self._sub(
            r"(?<![\d+])(?:\+7|8|7)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)", "ТЕЛЕФОН", text
        )
        text = self._sub(r"\+\d{1,3}(?:[\s\-()]*\d{2,4}){3,5}(?!\d)", "ТЕЛЕФОН", text)
        text = self._sub(
            r"(?i)(?:дата\s+рождения|д\.\s?р\.|родил(?:ся|ась))\s*[:\-—]?\s*(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
            "ДАТА_РОЖДЕНИЯ",
            text,
            group=1,
        )
        text = self._sub(r"\b(?:19|20)\d{2}\s?г\.\s?р\.", "ДАТА_РОЖДЕНИЯ", text)
        text = self._sub(
            r"(?i)\b(?:ул\.|улица|пр-т|проспект|пер\.|переулок|шоссе|б-р|бульвар|наб\.|набережная|проезд|пл\.|площадь"
            r"|мкр\.?|микрорайон)\s*[А-ЯЁA-Z0-9][^,\n;()]{1,40}"
            r"(?:,?\s*(?:д\.|дом)\s*\d+[а-яА-Я]?(?:\s*[,/]?\s*(?:к\.|корп\.|корпус|стр\.|строение)\s*\d+)?)?"
            r"(?:,?\s*(?:кв\.|квартира|оф\.|офис)\s*\d+)?",
            "АДРЕС",
            text,
        )
        text = self._sub(r"(?i)\bд\.\s*\d+[а-я]?,?\s*кв\.\s*\d+", "АДРЕС", text)
        text = self._sub(r"\b[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\s?\d{2,3}\b", "ДОКУМЕНТ", text)
        return self._names(text)

    def _cards(self, text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            value = match.group(0)
            digits = re.sub(r"\D", "", value)
            grouped = bool(re.fullmatch(r"\d{4}(?:[ -]\d{4}){3,4}", value.strip()))
            if not 13 <= len(digits) <= 19 or not (grouped or _luhn(digits)):
                return value
            return self._placeholder("КАРТА", match.group(0))

        return re.sub(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)", replace, text)

    def _names(self, text: str) -> str:
        for name in sorted({n.strip() for n in self.known_names if n and len(n.strip()) >= 3}, key=len, reverse=True):
            text = self._sub(rf"(?i)(?<![\w\[])(?:{_name_forms(name)})(?![\w\]])", "ИМЯ", text)
        # ФИО с отчеством: «Петров Иван Сергеевич», «Иван Сергеевич Петров», «Иван Сергеевич».
        text = self._sub(rf"\b{_CAP}\s+{_CAP}\s+{_PATRONYMIC}\b", "ИМЯ", text)
        text = self._sub(rf"\b{_CAP}\s+{_PATRONYMIC}(?:\s+{_SURNAME_ANY})?\b", "ИМЯ", text)
        # Фамилия с инициалами: «Петров И.С.», «И. С. Петров».
        text = self._sub(rf"\b{_SURNAME_ANY}\s+{_INITIALS}", "ИМЯ", text)
        text = self._sub(rf"\b{_INITIALS}\s?{_SURNAME_ANY}\b", "ИМЯ", text)
        # Распространённое имя, возможно с фамилией рядом: «Ольга Смирнова», «Смирнову Ольгу».
        name = rf"(?i:(?:{_FIRST_NAME_FORMS}))"
        text = self._sub(rf"(?<![\w\[])(?:{_SURNAME}\s+)?(?=[А-ЯЁ][а-яё]){name}(?:\s+{_SURNAME_ANY})?(?![\w\]])", "ИМЯ", text)
        # После слов, за которыми идёт человек: «зовут Лейла», «ИП Каримов», «гражданин Нуриев».
        text = self._sub(
            rf"(?i:\b(?:зовут|фамилия|гражданин|гражданка|ип|истец|истица|ответчик|ответчица|директор|доверитель)\s+)"
            rf"({_CAP}(?:\s+{_CAP}){{0,2}})",
            "ИМЯ",
            text,
            group=1,
        )

        def surname(match: re.Match[str]) -> str:
            if match.group(0).lower().startswith(_NOT_SURNAME_STEMS):
                return match.group(0)
            return self._placeholder("ИМЯ", match.group(0))

        return re.sub(rf"(?<![\w\[]){_SURNAME}(?![\w\]])", surname, text)

    def restore(self, text: str) -> str:
        if not text or not self.mapping:
            return text

        def replace(match: re.Match[str]) -> str:
            placeholder = f"[{match.group(1)}_{match.group(2)}]"
            return self.mapping.get(placeholder, match.group(0))

        return _PLACEHOLDER_RE.sub(replace, text)


class StreamRestorer:
    """Возвращает метки в потоковом ответе: метку, разрезанную между кусками, дожидается целиком."""

    def __init__(self, masker: Masker) -> None:
        self.masker = masker
        self._buffer = ""

    def feed(self, chunk: str) -> str:
        self._buffer += chunk or ""
        cut = self._buffer.rfind("[")
        if cut != -1 and "]" not in self._buffer[cut:] and len(self._buffer) - cut <= 32:
            ready, self._buffer = self._buffer[:cut], self._buffer[cut:]
        else:
            ready, self._buffer = self._buffer, ""
        return self.masker.restore(ready)

    def flush(self) -> str:
        ready, self._buffer = self._buffer, ""
        return self.masker.restore(ready)


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def mask_messages(messages: list[dict[str, str]], masker: Masker, *, keep_system: bool = True) -> list[dict[str, str]]:
    """Копия сообщений с обезличенным текстом; системные (наши промпты) — как есть."""
    masked: list[dict[str, str]] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str) and not (keep_system and message.get("role") == "system"):
            message = {**message, "content": masker.mask(content)}
        masked.append(message)
    if masker.mapping:
        masked.insert(1 if masked and masked[0].get("role") == "system" else 0, {"role": "system", "content": MASK_NOTE})
    return masked
