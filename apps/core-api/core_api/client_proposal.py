"""Сообщение клиенту о подготовленном договоре.

Единственное место, где собирается это сообщение. Раньше текст и кнопки жили в
боте, и любая отправка из другого места (например, из рабочего места юриста)
означала бы вторую копию. За последнюю неделю расхождение копий уже дважды
приводило к тихим сбоям, поэтому текст собирается здесь, а бот и мини-апп
вызывают одну и ту же доставку.

callback_data кнопок — договорённость с ботом: он их обрабатывает. Менять
строки нельзя, не меняя обработчик.
"""

from __future__ import annotations

import json

STATUS_LABELS: dict[str, str] = {
    "draft": "Черновик",
    "sent": "Отправлен",
    "viewed": "Просмотрен",
    "signed": "Подписан",
    "declined": "Отклонён",
    "expired": "Истёк",
    "superseded": "Заменён",
    "cancelled": "Отменён",
}


def build_summary(agreement: dict) -> str:
    """Короткая выжимка условий — то, что клиент видит до открытия документа."""
    details = "заполнены" if agreement.get("client_details_complete") else "нужно заполнить"
    status = agreement.get("status") or ""
    return (
        f"Договор № {agreement.get('agreement_number') or 'без номера'}\n"
        f"Статус: {STATUS_LABELS.get(status, status or 'неизвестен')}\n"
        f"Предмет: {agreement.get('subject') or 'не указан'}\n"
        f"Стоимость: {agreement.get('price_text') or 'не указана'}\n"
        f"Оплата: {agreement.get('payment_terms') or 'не указана'}\n"
        f"Данные клиента: {details}"
    )


def build_proposal_text(agreement: dict) -> str:
    """Полное сообщение при отправке договора клиенту."""
    return (
        "Юрист подготовил проект договора.\n\n"
        + build_summary(agreement)
        + "\n\nЗаполните свои реквизиты. После этого бот сформирует точную "
        "редакцию для проверки и подписания."
    )


def build_proposal_markup(agreement_id: str) -> str:
    """Кнопки под сообщением, готовые к отправке в Telegram."""
    return json.dumps(
        {
            "inline_keyboard": [
                [{"text": "Заполнить данные и открыть проект", "callback_data": f"sa_c:open:{agreement_id}"}],
                [{"text": "Задать вопрос", "callback_data": f"sa_c:q:{agreement_id}"}],
                [{"text": "Отказаться", "callback_data": f"sa_c:no:{agreement_id}"}],
            ]
        },
        ensure_ascii=False,
    )


def build_reply_text(agreement: dict, text: str) -> str:
    """Ответ юриста на вопрос клиента по договору."""
    number = agreement.get("agreement_number") or ""
    header = f"Ответ юриста по договору № {number}" if number else "Ответ юриста"
    return f"{header}\n\n{text}"
