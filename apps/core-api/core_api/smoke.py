"""Проверочные заявки после деплоя — не клиенты.

После выкладки сайт проверяли настоящей заявкой, и она оседала среди
клиентов: четыре таких «клиента» месяцами висели в списке и в воронке.
Договорённость: у проверочной заявки в utm есть слово smoke (например,
utm_source=smoke). Такую ядро сразу кладёт в архив с пометкой [SMOKE] и не
будит юриста уведомлением. Проверка при этом проходит по-настоящему: запись
создаётся, ответ тот же.
"""

from __future__ import annotations

import re

_SMOKE = re.compile(r"smoke", re.IGNORECASE)
MARK = "[SMOKE]"


def is_smoke(*utm_values: str | None) -> bool:
    return any(value and _SMOKE.search(value) for value in utm_values)


def mark_notes(notes: str | None) -> str:
    return MARK if not notes else f"{MARK}\n{notes}"
