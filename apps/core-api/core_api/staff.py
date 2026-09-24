"""Аккаунты владельца практики — их обращения считаются тестом.

Владелец проверяет клиентский путь со своих же аккаунтов Telegram: пишет
боту, подписывает NDA и договоры. Для системы это были обычные клиенты —
они попадали в деньги и счётчики, будили уведомления о новом лиде и
копились в списке. Здесь одно место, где решается, что это не клиент.
"""

from __future__ import annotations

from sqlalchemy import or_, true

from core_api.config import get_settings


def staff_telegram_ids() -> frozenset[int]:
    settings = get_settings()
    ids: set[int] = set()
    raw_ids = (
        settings.admin_telegram_id,
        *str(settings.lawyer_telegram_ids or "").split(","),
        # Тестовые аккаунты — без прав владельца, но и не клиенты.
        *str(settings.test_telegram_ids or "").split(","),
    )
    for raw in raw_ids:
        text = str(raw or "").strip()
        if text.isdigit():
            ids.add(int(text))
    return frozenset(ids)


def is_staff(telegram_user_id: int | None) -> bool:
    return telegram_user_id is not None and telegram_user_id in staff_telegram_ids()


def real_client(column):
    """Условие «не аккаунт владельца» для колонки telegram_user_id.

    NOT IN по NULL дал бы NULL: клиент без Telegram (с сайта) выпал бы из
    выборки, поэтому он оговорён отдельно.
    """
    staff = staff_telegram_ids()
    if not staff:
        return true()
    return or_(column.is_(None), column.not_in(staff))
