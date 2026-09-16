"""Интент-роутер: перед ответом определяем, о чём вообще сообщение.

До этого модуля каждое сообщение вело через воронку discover→diagnose→
qualify→propose по жёстким ключевым словам (funnel.py) — даже когда человек
продолжает своё дело, спрашивает про саму платформу, описывает задачу на
разработку или просто знакомится. Воронка не знает разницы и всё равно
строит «диагностический вывод + один уточняющий вопрос» под покупку системы
для юридического отдела.

Здесь — лёгкая LLM-классификация (ai_brain.classify_intent_async) с тихим
откатом к сегодняшнему поведению при любом сбое или низкой уверенности:
ответ клиенту важнее точной категоризации. sales_conversation — категория
по умолчанию, она же «ничего не меняем» для вызывающего кода.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import ai_brain

logger = logging.getLogger(__name__)

INTENTS = (
    "continuing_own_matter",
    "new_legal_task",
    "platform_question",
    "dev_task",
    "browsing",
    "sales_conversation",
)

DEFAULT_INTENT = "sales_conversation"
_MIN_CONFIDENCE = 0.5


@dataclass(frozen=True)
class IntentResult:
    intent: str
    confidence: float
    # None → вызывающий код ведёт себя как раньше (продажная воронка,
    # funnel.build_stage_context + funnel.enforce_leadgen_response).
    context_override: str | None


def _context_for(intent: str, *, has_core_context: bool) -> str | None:
    if intent == "continuing_own_matter":
        if not has_core_context:
            # Модель решила, что это продолжение дела, но своих данных о
            # человеке в ядре нет — не рискуем подставлять неверный кадр,
            # откатываемся к обычной воронке.
            return None
        return (
            "# Продолжение своего дела\n"
            "Судя по сообщению, человек продолжает разговор о своём деле, а не начинает "
            "новый холодный контакт. Отвечай по существу его вопроса, используя данные о "
            "нём выше. Не начинай с дискавери-вопросов (размер команды, бюджет, отрасль) — "
            "это не подходит для продолжения уже идущей работы. Если для ответа не хватает "
            "конкретики — уточни только то, что нужно по сути его вопроса."
        )
    if intent == "new_legal_task":
        return (
            "# Новая правовая задача\n"
            "Человек впервые описывает конкретную правовую задачу или вопрос. Дай короткий "
            "содержательный отклик по сути сказанного, затем предложи оформить обращение "
            "юристу — либо кнопкой «⚖️ Юридическая помощь», либо прямо продолжив здесь, если "
            "он уже начал описывать задачу. Не веди через воронку продажи автоматизации "
            "(размер команды, объём договоров, бюджет) — это разовая задача клиента, а не "
            "покупка системы для юридического отдела."
        )
    if intent == "dev_task":
        return (
            "# Задача на разработку\n"
            "Человек описывает задачу на разработку (бот, сайт, интеграция, AI-модуль, "
            "программа). Ответь по существу, приведи короткий релевантный пример из "
            "инженерной практики AI Verdict, предложи следующий шаг для обсуждения задачи. "
            "Не задавай вопросы продажной квалификации, если человек ещё не сформулировал "
            "бюджет и сроки сам."
        )
    if intent == "platform_question":
        return (
            "# Вопрос о платформе\n"
            "Человек спрашивает про саму компанию/платформу/тарифы/устройство сервиса, а не "
            "описывает свою задачу. Ответь прямо и по существу, ссылайся на реальные части "
            "платформы (Contract AI, юридическая и инженерная практики, новостной контур). "
            "Не квалифицируй его как лида и не дави предложением консультации, если он сам "
            "не просит связать с командой."
        )
    if intent == "browsing":
        return (
            "# Знакомство с платформой\n"
            "Человек, похоже, просто знакомится, а не пришёл с конкретной задачей. Будь "
            "лёгким и информативным: коротко покажи, что умеет AI Verdict, без давления "
            "вопросами квалификации. Дай понять, что можно и просто спросить, и сразу "
            "описать задачу."
        )
    return None  # sales_conversation и всё незнакомое — воронка как раньше


async def classify(
    *,
    conversation_history: list[dict],
    has_core_context: bool,
) -> IntentResult:
    """Классифицирует последнее сообщение. Любой сбой классификации или низкая
    уверенность — тихий откат к sales_conversation (context_override=None)."""
    try:
        raw = await ai_brain.ai_brain.classify_intent_async(conversation_history)
    except Exception as error:  # noqa: BLE001 — классификация необязательна, ответ важнее
        logger.warning("Intent classification raised, falling back to sales funnel: %s", error)
        raw = None

    intent = raw.get("intent") if isinstance(raw, dict) else None
    if intent not in INTENTS:
        intent = DEFAULT_INTENT

    confidence = 0.0
    if isinstance(raw, dict):
        try:
            confidence = float(raw.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0

    if confidence < _MIN_CONFIDENCE:
        intent = DEFAULT_INTENT

    return IntentResult(
        intent=intent,
        confidence=confidence,
        context_override=_context_for(intent, has_core_context=has_core_context),
    )
