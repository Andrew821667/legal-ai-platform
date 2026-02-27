"""
Логика этапов диалога и A/B CTA для контентной воронки.
"""

from __future__ import annotations

from typing import Dict, Optional


STAGES = ("discover", "diagnose", "qualify", "propose", "handoff")
_STAGE_INDEX = {name: idx for idx, name in enumerate(STAGES)}


_HANDOFF_HINTS = (
    "свяжите",
    "поговорить с человеком",
    "живой человек",
    "консультац",
    "созвон",
    "встреч",
    "как начать",
    "когда можем начать",
)


_NEXT_STEP_HINTS = (
    "стоимост",
    "цена",
    "бюджет",
    "срок",
    "как начать",
    "созвон",
    "консультац",
)


_PAIN_HINTS = (
    "не систематиз",
    "несистематиз",
    "по разному",
    "хаос",
    "теря",
    "пропуска",
    "ручн",
    "нет контроля",
    "непонятно",
    "не успева",
    "долго отвеч",
    "медленно",
)


_SERVICE_HINTS = (
    "заявк",
    "лид",
    "договор",
    "контракт",
    "суд",
    "претенз",
    "комплаенс",
    "юр",
    "юрид",
)


_CTA_HINTS = (
    "консультац",
    "созвон",
    "аудит",
    "следующий шаг",
    "передам команде",
    "свяж",
)


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def normalize_stage(stage: Optional[str]) -> str:
    if stage in _STAGE_INDEX:
        return stage  # type: ignore[return-value]
    return "discover"


def choose_cta_variant(user_id: int) -> str:
    """Детерминированное A/B деление для пользователя."""
    return "A" if user_id % 2 == 0 else "B"


def advance_stage(current_stage: Optional[str], target_stage: Optional[str]) -> str:
    current = normalize_stage(current_stage)
    target = normalize_stage(target_stage)
    if _STAGE_INDEX[target] >= _STAGE_INDEX[current]:
        return target
    return current


def infer_stage(
    previous_stage: Optional[str],
    user_message: str,
    lead_data: Optional[Dict],
    handoff_triggered: bool = False,
) -> str:
    """Простая эвристика переходов по этапам воронки."""
    lead_data = lead_data or {}
    message = (user_message or "").lower()

    has_service = bool(lead_data.get("service_category") or lead_data.get("specific_need")) or _contains_any(
        message,
        _SERVICE_HINTS,
    )
    has_pain = bool((lead_data.get("pain_point") or "").strip()) or _contains_any(message, _PAIN_HINTS)
    has_contact = bool(lead_data.get("email") or lead_data.get("phone"))

    qualification_fields = (
        lead_data.get("team_size"),
        lead_data.get("contracts_per_month"),
        lead_data.get("budget"),
        lead_data.get("urgency"),
        lead_data.get("industry"),
        lead_data.get("company"),
    )
    qualification_count = sum(1 for value in qualification_fields if value)

    asks_handoff = any(token in message for token in _HANDOFF_HINTS)
    asks_next_step = any(token in message for token in _NEXT_STEP_HINTS)

    if handoff_triggered or (has_contact and asks_handoff):
        target = "handoff"
    elif has_contact and asks_next_step and (has_pain or has_service):
        target = "handoff"
    elif has_pain and (qualification_count >= 2 or has_contact):
        target = "propose"
    elif has_pain or has_service:
        target = "qualify" if has_pain else "diagnose"
    else:
        target = "discover"

    return advance_stage(previous_stage, target)


def build_stage_context(stage: str, cta_variant: str, cta_shown: bool) -> str:
    """
    Генерирует дополнительный system-context для текущего этапа.
    """
    stage = normalize_stage(stage)
    variant = cta_variant if cta_variant in ("A", "B") else "A"

    lines = [
        f"Текущий этап: {stage}.",
        "Следуй этапу и не перескакивай через уточняющие вопросы.",
        "Не называй этапы пользователю напрямую.",
        "Избегай расплывчатых формулировок: давай конкретику и следующий шаг.",
    ]

    if stage == "discover":
        lines.append("Цель: зафиксировать контекст и быстро подсветить узкое место процесса.")
        lines.append("Сначала дай короткий диагностический вывод по словам клиента.")
        lines.append("Потом задай один вопрос с вариантами (1/2/3), а не общий открытый вопрос.")
    elif stage == "diagnose":
        lines.append("Цель: зафиксировать основную боль и бизнес-последствия.")
        lines.append("Добавь 1 строку про потери: сроки, конверсия, контроль качества.")
        lines.append("Задай один вопрос с вариантами: что критичнее - скорость, риски или загрузка.")
    elif stage == "qualify":
        lines.append("Цель: собрать недостающие поля квалификации (команда, объем, срок, бюджет, контакт).")
        lines.append("Проси только один недостающий параметр за сообщение, лучше в формате выбора.")
    elif stage == "propose":
        lines.append("Цель: предложить один релевантный формат решения и закрыть на действие.")
        if not cta_shown:
            if variant == "A":
                lines.append("В конце добавь мягкий переход к консультации 30 минут без запроса контактов в тексте.")
            else:
                lines.append("В конце добавь мягкий переход: быстрый аудит процесса + консультация 30 минут, без запроса контактов.")
    else:
        lines.append("Цель: подтвердить передачу команде и зафиксировать следующий контакт.")
        lines.append("Ответ должен быть коротким и конкретным.")

    return "\n".join(lines)


def is_cta_shown(response_text: str, variant: str) -> bool:
    text = (response_text or "").lower()
    if variant == "B":
        return (
            ("аудит" in text and "консультац" in text)
            or ("быстрый аудит" in text)
            or ("мини-аудит" in text and ("email" in text or "телефон" in text))
        )
    return (
        ("консультац" in text and "30" in text)
        or ("созвон" in text and "консультац" in text)
        or ("мини-аудит" in text and ("email" in text or "телефон" in text))
    )


def _first_qualification_question(lead_data: Optional[Dict]) -> str:
    lead_data = lead_data or {}

    if not lead_data.get("team_size"):
        return (
            "Чтобы оценить объем внедрения, сколько юристов участвуют в обработке заявок?\n"
            "1) 1-3\n"
            "2) 4-10\n"
            "3) 10+"
        )
    if not lead_data.get("contracts_per_month"):
        return (
            "Какой входящий объем по заявкам/договорам в месяц?\n"
            "1) до 10\n"
            "2) 10-30\n"
            "3) 30-50\n"
            "4) 50+"
        )
    if not lead_data.get("urgency"):
        return (
            "По срокам внедрения что приоритетнее?\n"
            "1) Срочно (1-2 недели)\n"
            "2) В этом месяце\n"
            "3) В горизонте квартала"
        )
    if not lead_data.get("budget"):
        return (
            "Чтобы предложить реалистичный формат, нужен ориентир бюджета:\n"
            "1) до 100K\n"
            "2) 100-300K\n"
            "3) 300-500K\n"
            "4) 500K+"
        )
    if not (lead_data.get("email") or lead_data.get("phone")):
        return "Если готовы к следующему шагу, можем перейти к консультации 30 минут по вашему кейсу."

    return (
        "Если ок, следующий шаг: мини-аудит процесса + консультация 30 минут.\n"
        "Подойдет такой формат?"
    )


def enforce_leadgen_response(
    response_text: str,
    stage: str,
    user_message: str,
    cta_shown: bool,
    cta_variant: str,
    lead_data: Optional[Dict] = None,
) -> str:
    """
    Пост-обработка ответа, чтобы не терять лидогенеративный ритм.
    """
    text = (response_text or "").strip()
    if not text:
        return text

    normalized_stage = normalize_stage(stage)
    user_lower = (user_message or "").lower()
    text_lower = text.lower()

    additions: list[str] = []
    has_structured_options = "1)" in text_lower or "2)" in text_lower
    pain_signal = _contains_any(user_lower, _PAIN_HINTS)

    if pain_signal and "типич" not in text_lower and "узкое место" not in text_lower:
        additions.append(
            "Это типичный сигнал разрозненного процесса: часть заявок теряется между каналами, "
            "а контроль сроков и статусов становится непрозрачным."
        )

    if normalized_stage in ("discover", "diagnose") and not has_structured_options:
        additions.append(
            "Чтобы быстро собрать рабочий план, где сейчас основной провал?\n"
            "1) Медленный первый ответ клиенту\n"
            "2) Хаотичное распределение заявок между юристами\n"
            "3) Нет контроля статусов и дедлайнов"
        )

    if normalized_stage == "qualify" and not has_structured_options:
        additions.append(_first_qualification_question(lead_data))

    # CTA в тексте минимизируем: следующий шаг показывается интерфейсной кнопкой.

    if not additions:
        return text

    return f"{text}\n\n" + "\n\n".join(additions)


def should_show_consultation_button(stage: str, cta_shown: bool) -> bool:
    """
    Показываем отдельную кнопку консультации вместо навязчивого CTA в тексте.
    """
    if cta_shown:
        return False
    normalized_stage = normalize_stage(stage)
    return normalized_stage in ("qualify", "propose", "handoff")
