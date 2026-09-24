"""Кто в боте владелец практики.

Раньше владельцем был один аккаунт — ADMIN_TELEGRAM_ID, и сравнение с ним
стояло в каждом обработчике. Владелец же проверяет клиентский путь со
второго аккаунта, и тот для бота был чужим: ни /admin, ни кнопок юриста.

Два вопроса, и они разные:
- права владельца (админ-команды, кнопки юриста, рабочее пространство) —
  у основного и у дополнительных аккаунтов (LAWYER_TELEGRAM_IDS);
- клиентский путь (согласие на ПД, клиентское меню, лиды) — у
  дополнительных аккаунтов как у клиента: с них он и проверяется.

Функции принимают конфиг параметром: тесты подменяют его простым
объектом, и метод на классе Config там бы не нашёлся.
"""

from __future__ import annotations


def is_admin_user(config, user_id: int | None) -> bool:
    """Права владельца: основной аккаунт или дополнительный."""
    if user_id is None:
        return False
    extra = getattr(config, "LAWYER_TELEGRAM_IDS", None) or ()
    return user_id == getattr(config, "ADMIN_TELEGRAM_ID", None) or user_id in extra


def is_extra_admin(config, user_id: int | None) -> bool:
    """Дополнительный аккаунт: права владельца и при этом клиентские кнопки."""
    if user_id is None:
        return False
    return user_id in (getattr(config, "LAWYER_TELEGRAM_IDS", None) or ())
