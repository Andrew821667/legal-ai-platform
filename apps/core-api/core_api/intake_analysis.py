"""Разбор юридического обращения языковой моделью.

Обращения приходят короткими: клиент описывает ситуацию в двух-трёх фразах.
Задача разбора — не заменить юриста, а подготовить его работу: назвать область
права, отметить срочность, перечислить недостающие документы и вопросы,
которые стоит задать.

Модель намеренно не даёт правовых оценок и не советует, что делать. Такой
вывод был бы консультацией, ответственность за которую несёт юрист, а не
машина. Границы заданы в системном промпте и проверяются тестами.

Сам вызов вендора живёт в model_client: у модели два потребителя — этот разбор
и помощник, ведущий диалог с клиентом, — и прокси с учётом стоимости должны
меняться в одном месте.
"""

from __future__ import annotations

import logging

from core_api.model_client import (
    DEFAULT_MODEL,
    MODEL_PRICING,
    ChatResult,
    chat,
    estimate_cost,
    format_cost,
)

logger = logging.getLogger(__name__)

# Совместимость: модуль исторически экспортировал эти имена, и на них
# ссылаются уведомления юристу и тесты.
__all__ = [
    "DEFAULT_MODEL",
    "MODEL_PRICING",
    "AnalysisResult",
    "analyze_intake",
    "estimate_cost",
    "format_cost",
]

AnalysisResult = ChatResult

SYSTEM_PROMPT = (
    "Ты — помощник юридической практики AI Verdict. Ты готовишь материал для юриста "
    "по обращению клиента.\n\n"
    "Сделай краткий разбор по структуре:\n"
    "1. Суть обращения — одно-два предложения своими словами.\n"
    "2. Область права.\n"
    "3. Срочность и почему: есть ли признаки горящих сроков.\n"
    "4. Каких документов не хватает для полноценного разбора.\n"
    "5. Два-три уточняющих вопроса клиенту.\n"
    "6. На что юристу обратить внимание в первую очередь.\n\n"
    "Строгие ограничения:\n"
    "— не давай правовых оценок и не предсказывай исход дела;\n"
    "— не советуй клиенту, что делать;\n"
    "— не называй конкретные статьи и суммы, если их нет в обращении;\n"
    "— если данных мало, так и напиши, а не достраивай ситуацию догадками.\n\n"
    "Пиши по-русски, деловым языком, без канцелярита и без воды."
)


def _build_prompt(intake: dict[str, object]) -> str:
    parts = [f"Описание: {intake.get('description') or 'не указано'}"]
    for label, key in (
        ("Тип клиента", "client_type"),
        ("Область", "legal_area"),
        ("Срочность", "urgency"),
        ("Срок", "deadline"),
        ("Регион", "region"),
    ):
        value = intake.get(key)
        if value:
            parts.append(f"{label}: {value}")
    return "\n".join(parts)


def analyze_intake(
    intake: dict[str, object],
    *,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    model: str = DEFAULT_MODEL,
    proxy_url: str | None = None,
    timeout: float = 90.0,
    max_output_tokens: int = 900,
) -> AnalysisResult:
    """Отправляет обращение модели и возвращает разбор со стоимостью.

    Сбой разбора не должен ломать приём обращения: при любой ошибке
    возвращается результат с заполненным error, а вызывающая сторона просто
    отправляет уведомление без аналитики.
    """
    return chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(intake)},
        ],
        api_key=api_key,
        base_url=base_url,
        model=model,
        proxy_url=proxy_url,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
    )
