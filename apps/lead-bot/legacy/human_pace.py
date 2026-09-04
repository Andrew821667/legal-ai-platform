"""Темп, в котором помощник пишет клиенту.

Ответ, приходящий через долю секунды после вопроса, выдаёт машину вернее любой
формулировки: люди так не пишут. Причём дело не в правдоподобии ради него
самого — мгновенный ответ читается как отписка, а пауза с индикатором «печатает»
как внимание к сказанному.

Пауза считается от длины реплики: длинный ответ и печатать дольше. Сверху
жёсткий предел — человек ждёт в переписке, и заставлять его смотреть на
«печатает» полминуты ради достоверности было бы издевательством.
"""

from __future__ import annotations

import random

# Секунд на символ. Примерно соответствует уверенному набору на телефоне —
# около 350 знаков в минуту.
_SECONDS_PER_CHAR = 0.017

# Пауза на осмысление перед началом набора.
_THINKING_SECONDS = 0.8

# Границы. Нижняя — чтобы даже «Понял» не выскакивало мгновенно; верхняя —
# чтобы длинная реплика не превращалась в ожидание.
MIN_DELAY_SECONDS = 1.2
MAX_DELAY_SECONDS = 6.0

# Разброс: ровно одинаковые паузы сами по себе выглядят машинными.
_JITTER = 0.15


def typing_delay(text: str, *, jitter: bool = True) -> float:
    """Сколько секунд «печатать» эту реплику."""
    length = len(text or "")
    raw = _THINKING_SECONDS + length * _SECONDS_PER_CHAR
    if jitter:
        raw *= 1.0 + random.uniform(-_JITTER, _JITTER)
    return max(MIN_DELAY_SECONDS, min(MAX_DELAY_SECONDS, raw))


# Telegram гасит индикатор «печатает» примерно через пять секунд, поэтому для
# длинных пауз его нужно посылать повторно.
TYPING_REFRESH_SECONDS = 4.0


def typing_chunks(delay: float) -> list[float]:
    """Разбивает паузу на отрезки, между которыми обновляется индикатор."""
    chunks = []
    remaining = delay
    while remaining > TYPING_REFRESH_SECONDS:
        chunks.append(TYPING_REFRESH_SECONDS)
        remaining -= TYPING_REFRESH_SECONDS
    if remaining > 0:
        chunks.append(remaining)
    return chunks
