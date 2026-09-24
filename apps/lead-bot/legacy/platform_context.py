"""Контекст ядра платформы для системного промпта ассистента.

До этого модуля ассистент видел только: свою системную инструкцию, стадию
воронки и последние 20 сообщений текущего диалога — ничего о том, что уже
известно о собеседнике в ядре (обращения, NDA, договоры, акты). Отсюда два
живых бага: личное сообщение обрабатывалось как холодный лид, а ассистент не
узнавал человека, у которого уже есть открытое дело.

Здесь собирается только *собственная* история собеседника (по его
telegram_user_id, через тот же эндпоинт, что и у клиентского кабинета) —
чужие дела сюда не попадают, это отдельная, более рискованная задача
сопоставления однофамильцев (см. TODO в конце файла).
"""
from __future__ import annotations

import logging
from typing import Any

import database
from core_api_bridge import core_api_bridge

logger = logging.getLogger(__name__)

_LEGAL_AREA_LABELS = {
    "civil": "гражданское право",
    "family": "семейное право",
    "labor": "трудовое право",
    "corporate": "корпоративное право",
    "criminal": "уголовное право",
    "administrative": "административное право",
    "tax": "налоговое право",
    "real_estate": "недвижимость",
    "ip": "интеллектуальная собственность",
    "other": "иное",
}

_CASE_STATUS_LABELS = {
    "new": "новое",
    "in_progress": "в работе",
    "awaiting_client": "ждём клиента",
    "awaiting_documents": "ждём документы",
    "completed": "завершено",
    "closed": "закрыто",
    "cancelled": "отменено",
}

_AGREEMENT_STATUS_LABELS = {
    "sent": "отправлен клиенту",
    "viewed": "клиент открыл",
    "signed": "подписан",
    "declined": "клиент отклонил",
}

_ACT_STATUS_LABELS = {
    "sent": "отправлен клиенту",
    "viewed": "клиент открыл",
    "accepted": "принят клиентом",
    "objected": "клиент возразил",
    "paid": "оплачен",
    "cancelled": "отменён",
}

_MAX_CASES = 5
_MAX_AGREEMENTS = 5
_MAX_ACTS = 5
_DESCRIPTION_LIMIT = 300


def _date(value: str | None) -> str:
    if not value:
        return "дата неизвестна"
    return value[:10]


def _label(mapping: dict[str, str], value: Any) -> str:
    key = str(value or "").strip().lower()
    return mapping.get(key, key or "неизвестно")


def build_core_context_block(telegram_user_id: int | None) -> str:
    """Блок «что уже известно об этом человеке» для системного промпта.

    Пустая строка означает «своих данных в ядре нет» (человек обращается
    впервые) — в этом случае в промпт ничего не добавляется, поведение как
    раньше.
    """
    if not telegram_user_id or not core_api_bridge.enabled:
        return ""
    try:
        summary = core_api_bridge.client_portal_summary(int(telegram_user_id))
    except Exception as error:  # noqa: BLE001 — блок необязателен, ответ важнее
        logger.warning("Failed to load core context for %s: %s", telegram_user_id, error)
        return ""
    if not summary:
        return ""

    cases = summary.get("cases") or []
    agreements = summary.get("agreements") or []
    acts = summary.get("acts") or []
    nda = summary.get("nda") or {}

    if not cases and not agreements and not acts and not nda.get("signed"):
        return ""

    lines = [
        "# Собеседник уже известен платформе",
        "Это НЕ новый холодный контакт — ниже проверенные данные о его прошлых "
        "обращениях из ядра платформы. Учитывай их в ответе: не переспрашивай то, "
        "что уже известно, ссылайся на статус его дела своими словами, если это "
        "уместно по смыслу разговора.",
    ]

    if nda.get("signed"):
        lines.append(f"- NDA подписан {_date(nda.get('signed_at'))} (версия {nda.get('version') or '—'}).")

    for case in cases[:_MAX_CASES]:
        area = _label(_LEGAL_AREA_LABELS, case.get("legal_area"))
        status = _label(_CASE_STATUS_LABELS, case.get("status"))
        description = (case.get("description") or "").strip()[:_DESCRIPTION_LIMIT]
        line = f"- Обращение от {_date(case.get('created_at'))} ({area}, статус: {status})"
        if description:
            line += f": «{description}»"
        lines.append(line)
    if len(cases) > _MAX_CASES:
        lines.append(f"  …и ещё {len(cases) - _MAX_CASES} обращени(й) ранее.")

    for agreement in agreements[:_MAX_AGREEMENTS]:
        status = _label(_AGREEMENT_STATUS_LABELS, agreement.get("status"))
        subject = (agreement.get("subject") or "").strip()[:_DESCRIPTION_LIMIT]
        title = "Допсоглашение" if agreement.get("kind") == "supplement" else "Договор"
        line = f"- {title} № {agreement.get('number') or '—'} ({status})"
        if subject:
            line += f": {subject}"
        lines.append(line)
    if len(agreements) > _MAX_AGREEMENTS:
        lines.append(f"  …и ещё {len(agreements) - _MAX_AGREEMENTS} договор(ов).")

    for act in acts[:_MAX_ACTS]:
        status = _label(_ACT_STATUS_LABELS, act.get("status"))
        lines.append(f"- Акт № {act.get('number') or '—'} ({status}).")
    if len(acts) > _MAX_ACTS:
        lines.append(f"  …и ещё {len(acts) - _MAX_ACTS} акт(ов).")

    return "\n".join(lines)


def build_topic_memory_block(telegram_user_id: int | None) -> str:
    """Что человек уже обсуждал с ассистентом раньше — пункт 4 плана «умный
    ассистент». В отличие от build_core_context_block, не зависит от ядра и
    формальных дел: работает и для тех, у кого никогда не было ни обращения,
    ни NDA, но кто уже не раз что-то спрашивал у ассистента (например, узнавал
    про платформу, но не оставил заявку).
    """
    if not telegram_user_id:
        return ""
    try:
        user = database.db.get_user_by_telegram_id(int(telegram_user_id))
        if not user:
            return ""
        summary = database.db.get_topic_memory(user["id"])
    except Exception as error:  # noqa: BLE001 — блок необязателен, ответ важнее
        logger.warning("Failed to load topic memory for %s: %s", telegram_user_id, error)
        return ""
    if not summary:
        return ""
    return (
        "# Прошлые темы разговора\n"
        f"Ранее в переписке с ассистентом человек уже поднимал: {summary}\n"
        "Учитывай это как контекст, но не пересказывай дословно, если это не по теме сейчас."
    )


def build_full_case_details_block(telegram_user_id: int | None) -> str:
    """Полные данные о собеседнике — для инструмента `get_full_case_details`
    (assistant_tools.py), а не для проактивного блока промпта.

    В отличие от `build_core_context_block` — без ограничения в 5 штук и без
    обрезки описаний, плюс то, чего в кратком блоке вовсе нет: названия
    приложенных документов, переписка по договору с юристом, сумма и статус
    возражения по акту. Ассистент зовёт это, когда краткого блока не хватило
    для конкретного вопроса собеседника о своём деле.
    """
    if not telegram_user_id or not core_api_bridge.enabled:
        return "Данных об этом собеседнике в ядре платформы нет."
    try:
        summary = core_api_bridge.client_portal_summary(int(telegram_user_id))
    except Exception as error:  # noqa: BLE001 — инструмент не должен ронять ответ
        logger.warning("Failed to load full case details for %s: %s", telegram_user_id, error)
        return "Не удалось загрузить данные — ядро платформы сейчас недоступно."
    if not summary:
        return "Данных об этом собеседнике в ядре платформы нет."

    cases = summary.get("cases") or []
    agreements = summary.get("agreements") or []
    acts = summary.get("acts") or []
    nda = summary.get("nda") or {}

    if not cases and not agreements and not acts and not nda.get("signed"):
        return "Данных об этом собеседнике в ядре платформы нет."

    lines: list[str] = []

    if nda.get("signed"):
        lines.append(f"NDA подписан {_date(nda.get('signed_at'))} (версия {nda.get('version') or '—'}).")

    for case in cases:
        area = _label(_LEGAL_AREA_LABELS, case.get("legal_area"))
        status = _label(_CASE_STATUS_LABELS, case.get("status"))
        description = (case.get("description") or "").strip()
        lines.append(f"\nОбращение от {_date(case.get('created_at'))} ({area}, статус: {status})")
        if description:
            lines.append(f"  Текст обращения: «{description}»")
        documents = case.get("documents") or []
        if documents:
            names = ", ".join(f"{doc.get('file_name') or '—'} ({_date(doc.get('created_at'))})" for doc in documents)
            lines.append(f"  Приложенные документы: {names}")

    for agreement in agreements:
        status = _label(_AGREEMENT_STATUS_LABELS, agreement.get("status"))
        subject = (agreement.get("subject") or "").strip()
        lines.append(f"\nДоговор № {agreement.get('number') or '—'} ({status})")
        if subject:
            lines.append(f"  Предмет: {subject}")
        if agreement.get("price_text"):
            lines.append(f"  Стоимость: {agreement['price_text']}")
        for message in agreement.get("messages") or []:
            role = "Клиент" if message.get("role") == "client" else "Юрист"
            text = (message.get("text") or "").strip()
            if text:
                lines.append(f"  {role} ({_date(message.get('created_at'))}): «{text}»")

    for act in acts:
        status = _label(_ACT_STATUS_LABELS, act.get("status"))
        lines.append(f"\nАкт № {act.get('number') or '—'} ({status})")
        if act.get("description"):
            lines.append(f"  Описание работ: {act['description']}")
        if act.get("objection_text"):
            lines.append(f"  Возражение клиента: «{act['objection_text']}»")

    return "\n".join(lines).strip()


# TODO(контекстный ассистент, п.3): сопоставление с ЧУЖИМИ обращениями по
# фамилии/упоминанию (например, Рябова <-> Рябов) — риск конфликта интересов
# и утечки чужих данных в промпт, нужен отдельный, более осторожный дизайн
# (подтверждение владельцем, а не автоматическая подстановка в ответ клиенту).
# Лёгкая версия того же сигнала — только для владельца, без выхода в ответ
# клиенту — сделана в handlers/helpers.py (notify_admin_new_lead).
