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

import asyncio
import logging
from typing import Any, Awaitable, Callable

import core_api_bridge
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

# Только для веб-виджета сайта: у анонимного посетителя нет telegram_id,
# сопоставлять его с делом в ядре не с чем — пока он сам не заявит, что уже
# клиент, и не подтвердит это. Голого совпадения по контакту недостаточно
# (посторонний мог его узнать) — нужен ещё номер договора, то есть то, что
# знает только реальная сторона. См. core_api/routers/client_portal.py:verify.
IDENTIFY_RETURNING_CLIENT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "identify_returning_client",
        "description": (
            "Подтвердить, что собеседник — уже известный клиент, а не новый "
            "посетитель. Зови ТОЛЬКО когда человек САМ сказал, что уже "
            "обращался к нам/уже клиент, И назвал контакт (телефон или "
            "email), И номер своего договора — не спрашивай номер договора "
            "заранее без повода, это не стартовый вопрос для всех. Если "
            "verified=false в ответе — не говори человеку, что данные не "
            "совпали (это может выдать постороннему сам факт поиска по "
            "чужому контакту в базе) — просто продолжи как с обычным "
            "посетителем."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "contact": {
                    "type": "string",
                    "description": "Телефон или email, который назвал собеседник.",
                },
                "agreement_number": {
                    "type": "string",
                    "description": "Номер договора, который назвал собеседник.",
                },
            },
            "required": ["contact", "agreement_number"],
        },
    },
}


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


async def _identify_returning_client(arguments: dict[str, Any]) -> tuple[str, int | None]:
    contact = str(arguments.get("contact") or "").strip()
    agreement_number = str(arguments.get("agreement_number") or "").strip()
    if not contact or not agreement_number:
        return "Не хватает контакта или номера договора — уточни у собеседника оба.", None

    telegram_id = await asyncio.to_thread(
        core_api_bridge.core_api_bridge.verify_returning_client,
        contact=contact,
        agreement_number=agreement_number,
    )
    if telegram_id is None:
        return (
            "Не подтвердилось — контакт и номер договора не совпали ни с одной записью. "
            "Не сообщай собеседнику, что искал его в базе и не нашёл — просто продолжи "
            "разговор как с обычным посетителем сайта.",
            None,
        )
    return (
        "Подтверждено — это известный клиент. Данные о нём доступны через "
        "get_full_case_details, используй их в ответе.",
        telegram_id,
    )


class WebSessionState:
    """Mutable-состояние ОДНОГО HTTP-ответа веб-виджета (не переживает между
    запросами само по себе — за это отвечает вызывающий код в
    web_assistant_api.py). Нужно, чтобы get_full_case_details внутри ЭТОГО ЖЕ
    ответа увидел telegram_id, который identify_returning_client только что
    нашёл — без этого модели пришлось бы ждать следующего сообщения."""

    def __init__(self, telegram_id: int | None = None) -> None:
        self.telegram_id = telegram_id


def executor_for_web(state: WebSessionState) -> ToolExecutor:
    """Как executor_for, но telegram_id не фиксирован заранее — его может
    установить сам identify_returning_client в процессе этого же ответа."""

    async def _executor(name: str, arguments: dict[str, Any]) -> str:
        if name == "identify_returning_client":
            try:
                result_text, found_id = await _identify_returning_client(arguments)
            except Exception as error:  # noqa: BLE001 — инструмент не должен ронять ответ
                logger.warning("identify_returning_client failed: %s", error)
                return "Не удалось проверить данные — сообщи об этом собеседнику и продолжи без них."
            if found_id is not None:
                state.telegram_id = found_id
            return result_text
        return await execute(name, arguments, telegram_id=state.telegram_id)

    return _executor
