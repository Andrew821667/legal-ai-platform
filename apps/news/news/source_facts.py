"""Сверка «жёстких» фактов поста с текстом источника — кодом, без модели.

Канал публикует посты сам (решение владельца 01.10.2026: без ручной проверки,
но с усиленным автоматическим контролем). Проверка моделью ловит перепутанные
роли и устаревшие прогнозы, но не гарантирует, что номер закона, статья, дата
или сумма в посте взяты из источника, а не додуманы. Здесь каждое такое
значение ищется в заголовке и тексте источника; чего там нет — «не подтверждено».

Сервисные блоки поста («Следующий шаг» с нашими ценами, «Источник», хэштеги)
в сверку не входят: это наш текст, а не пересказ источника.
"""
from __future__ import annotations

import html
import re
import threading
import time
from collections import deque
from dataclasses import dataclass

_MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
    "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}
_MONTH_RE = r"(январ[ья]|феврал[ья]|марта?|апрел[ья]|ма[яй]|июн[ья]|июл[ья]|августа?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])"

_SERVICE_BLOCK_RE = re.compile(
    r"<b>\s*(?:Следующий шаг|Источник)\s*</b>.*?(?=<b>\s*(?:Следующий шаг|Источник)\s*</b>|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_HASHTAG_RE = re.compile(r"(?<!\w)#[\wА-Яа-яЁё_]+")
_TAG_RE = re.compile(r"<[^>]+>")

_LAW_RE = re.compile(r"(\d{1,4})\s*[-‑–—]\s*(ФКЗ|ФЗ)\b", re.IGNORECASE)
_ARTICLE_RE = re.compile(r"(?:\bст\.|\bстать[яиеюй]\w*)\s*(\d{1,4}(?:\.\d{1,3})?)", re.IGNORECASE)
_NUMBER_SIGN_RE = re.compile(r"№\s*([A-Za-zА-Яа-я]?\d[\w\-/.]*\w|\d)")
_TEXT_DATE_RE = re.compile(rf"\b(\d{{1,2}})\s+{_MONTH_RE}(?:\s+(\d{{4}}))?", re.IGNORECASE)
_NUM_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
# Число: разряды — только группами по три через пробел («20 000»), иначе
# «в 2025 17 компаний» склеилось бы в одно число.
_NUMBER = r"(?:\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,]\d+)?"
_AMOUNT_RE = re.compile(
    rf"({_NUMBER})\s*(%|процент\w*|₽|руб\w*|млн|млрд|трлн|тыс\w*|\$|долл\w*|€|евро)",
    re.IGNORECASE,
)
_ANY_NUMBER_RE = re.compile(_NUMBER)


def _plain(text: str) -> str:
    text = _TAG_RE.sub(" ", text or "")
    text = html.unescape(text).replace("ё", "е").replace("Ё", "Е")
    return re.sub(r"[   ]", " ", text)


def post_body(post_html: str) -> str:
    """Текст поста без «Следующего шага», «Источника» и хэштегов."""
    body = _SERVICE_BLOCK_RE.sub(" ", post_html or "")
    return _HASHTAG_RE.sub(" ", _plain(body))


def _number_key(raw: str) -> str:
    digits = re.sub(r"[\s  ]", "", raw).replace(",", ".")
    if "." in digits:
        digits = digits.rstrip("0").rstrip(".")
    return digits


def _month_number(word: str) -> int | None:
    lowered = word.lower()
    for stem, number in sorted(_MONTHS.items(), key=lambda item: -len(item[0])):
        if lowered.startswith(stem):
            return number
    return None


def _dates(text: str) -> set[tuple[int, int, int | None]]:
    found: set[tuple[int, int, int | None]] = set()
    for day, month_word, year in _TEXT_DATE_RE.findall(text):
        month = _month_number(month_word)
        if month and 1 <= int(day) <= 31:
            found.add((int(day), month, int(year) if year else None))
    for day, month, year in _NUM_DATE_RE.findall(text):
        found.add((int(day), int(month), int(year)))
    for year, month, day in _ISO_DATE_RE.findall(text):
        found.add((int(day), int(month), int(year)))
    return found


@dataclass(frozen=True)
class _SourceIndex:
    laws: set[str]
    articles: set[str]
    numbered: set[str]
    dates: set[tuple[int, int, int | None]]
    numbers: set[str]


def _index(text: str) -> _SourceIndex:
    plain = _plain(text)
    return _SourceIndex(
        laws={f"{number}-{kind.lower()}" for number, kind in _LAW_RE.findall(plain)},
        articles={key for key in _ARTICLE_RE.findall(plain)},
        numbered={value.lower().rstrip(".") for value in _NUMBER_SIGN_RE.findall(plain)},
        dates=_dates(plain),
        numbers={_number_key(raw) for raw in _ANY_NUMBER_RE.findall(plain)},
    )


def _date_supported(date: tuple[int, int, int | None], source: set[tuple[int, int, int | None]]) -> bool:
    day, month, year = date
    for s_day, s_month, s_year in source:
        if (s_day, s_month) != (day, month):
            continue
        if year is None or s_year is None or s_year == year:
            return True
    return False


def unsupported_facts(title: str, post_html: str, source_text: str, *, check_dates: bool = True) -> list[str]:
    """Номера законов и актов, статьи, даты и суммы из поста, которых нет в источнике.

    check_dates=False — для обзоров недели и дайджестов: там редакция сама
    пишет диапазон дат, которого нет в отдельных материалах."""
    text = f"{_plain(title)}\n{post_body(post_html)}"
    source = _index(source_text)
    problems: list[str] = []

    for number, kind in _LAW_RE.findall(text):
        if f"{number}-{kind.lower()}" not in source.laws:
            problems.append(f"{number}-{kind.upper()}")
    for key in _ARTICLE_RE.findall(text):
        if key not in source.articles:
            problems.append(f"ст. {key}")
    for value in _NUMBER_SIGN_RE.findall(text):
        normalized = value.lower().rstrip(".")
        if normalized not in source.numbered and not _LAW_RE.fullmatch(value):
            problems.append(f"№ {value}")
    for date in _dates(text) if check_dates else ():
        if not _date_supported(date, source.dates):
            day, month, year = date
            problems.append(f"{day:02d}.{month:02d}" + (f".{year}" if year else ""))
    for raw, unit in _AMOUNT_RE.findall(text):
        key = _number_key(raw)
        if key and key not in source.numbers:
            problems.append(f"{raw.strip()} {unit}")

    seen: set[str] = set()
    return [item for item in problems if not (item in seen or seen.add(item))]


# ── Журнал контроля для ежедневного отчёта админ-бота ─────────────────────────

_JOURNAL_DAYS = 7
_journal: deque[tuple[float, str, str]] = deque(maxlen=500)
_journal_lock = threading.Lock()


def record(outcome: str, title: str = "") -> None:
    """outcome: checked — всё подтверждено; repaired — неподтверждённое убрано
    повторной правкой; rejected — пост не создан."""
    with _journal_lock:
        _journal.append((time.time(), outcome, (title or "")[:90]))


def journal_summary(now: float | None = None) -> dict[str, object]:
    cutoff = (now or time.time()) - _JOURNAL_DAYS * 86400
    with _journal_lock:
        rows = [row for row in _journal if row[0] >= cutoff]
    counts = {outcome: sum(1 for _, kind, _ in rows if kind == outcome) for outcome in ("checked", "repaired", "rejected")}
    rejected_titles = [title for _, kind, title in reversed(rows) if kind == "rejected" and title][:3]
    return {"days": _JOURNAL_DAYS, **counts, "rejected_titles": rejected_titles}
