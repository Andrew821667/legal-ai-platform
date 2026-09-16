"""Инструменты (function calling) ассистента — пункт 2 плана «умный ассистент».

До этого модуля ассистент мог только рассказывать о возможностях платформы,
но не мог сам ничего посмотреть или сделать. Первый инструмент нарочно на
уже существующих, проверенных данных (тот же источник, что
`platform_context.build_core_context_block` — client-portal/summary из
ядра): без новой внешней системы, без риска расхода бюджета на LLM или
злоупотребления — только чтение своих же данных собеседника.

Ассистент зовёт `get_full_case_details`, когда краткого проактивного блока
контекста не хватило для конкретного вопроса — например, собеседник
спрашивает, что именно он прикладывал к обращению, или что писал юристу по
договору.

Дальше по плану (Current.md, п.2): черновик обращения с подтверждением
кнопкой и разбор договора через Contract AI — оба требуют отдельного
дизайна (черновик+подтверждение и, для разбора, защиты от злоупотребления
загрузками) и сюда пока не входят.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

import platform_context

logger = logging.getLogger(__name__)

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_full_case_details",
            "description": (
                "Вернуть ПОЛНЫЕ данные о собственных делах текущего собеседника в "
                "системе: все его обращения целиком (не только последние, без "
                "обрезки текста), приложенные документы, переписка по договору с "
                "юристом, акты. Зови, когда в контексте выше данных не хватает — "
                "например, собеседник спрашивает про конкретную деталь своего "
                "обращения, которой нет в кратком списке, какие документы он "
                "присылал, или что обсуждалось по его договору."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[str]]


async def execute(name: str, arguments: dict[str, Any], *, telegram_id: int | None) -> str:
    """Единая точка выполнения инструмента.

    Любой сбой — текст с объяснением, а не исключение: инструмент не должен
    ронять весь ответ клиенту, модель просто увидит, что данные недоступны,
    и ответит без них.
    """
    try:
        if name == "get_full_case_details":
            return platform_context.build_full_case_details_block(telegram_id)
        logger.warning("Unknown tool requested by model: %s", name)
        return f"Инструмент «{name}» не существует."
    except Exception as error:  # noqa: BLE001 — инструмент не должен ронять ответ
        logger.warning("Tool %s failed for telegram_id=%s: %s", name, telegram_id, error)
        return "Не удалось получить данные из ядра платформы — сообщи об этом собеседнику и ответь без них."


def executor_for(telegram_id: int | None) -> ToolExecutor:
    """Замыкание с telegram_id собеседника — то, что реально уходит в generate_response_stream."""

    async def _executor(name: str, arguments: dict[str, Any]) -> str:
        return await execute(name, arguments, telegram_id=telegram_id)

    return _executor
