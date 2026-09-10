"""Команды в кнопке меню.

Раньше бот не задавал их вовсе: кнопка меню была пуста, и об админ-панели можно
было узнать, только зная, что набрать «/admin». Эти проверки закрепляют, что
меню заполняется и что админские команды не показываются клиенту.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import bot as bot_module


def test_client_menu_stays_short() -> None:
    """Длинный перечень в мессенджере читается как свалка, и нужное теряется."""
    assert 3 <= len(bot_module.CLIENT_COMMANDS) <= 6


def test_admin_sees_the_panel_first() -> None:
    """Ради этой команды меню и заводилось — она должна быть сверху."""
    assert bot_module.ADMIN_COMMANDS[0].command == "admin"


def test_client_does_not_see_admin_commands() -> None:
    client = {c.command for c in bot_module.CLIENT_COMMANDS}
    for hidden in ("admin", "stats", "leads"):
        assert hidden not in client, hidden


def test_every_menu_command_has_a_handler() -> None:
    """Команда в меню, которую бот не обрабатывает, — обещание без исполнения."""
    import inspect

    source = inspect.getsource(bot_module.build_application)
    for command in {c.command for c in bot_module.ADMIN_COMMANDS}:
        assert f'CommandHandler("{command}"' in source, command


class _Bot:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.calls: list[tuple[int, object]] = []
        self._fail = fail

    async def set_my_commands(self, commands, scope=None):
        if self._fail is not None:
            raise self._fail
        self.calls.append((len(commands), type(scope).__name__))


@pytest.mark.anyio
async def test_menu_is_set_for_both_audiences(monkeypatch) -> None:
    monkeypatch.setattr(bot_module.config, "ADMIN_TELEGRAM_ID", 42, raising=False)
    bot = _Bot()
    await bot_module._set_command_menu(SimpleNamespace(bot=bot))

    scopes = [scope for _, scope in bot.calls]
    assert "BotCommandScopeDefault" in scopes
    assert "BotCommandScopeChat" in scopes


@pytest.mark.anyio
async def test_network_failure_does_not_block_startup(monkeypatch) -> None:
    """Меню — украшение интерфейса, а не условие работы.

    Раньше подобная ошибка роняла запуск модератора новостей: бот уходил в
    перезапуск, хотя принимать сообщения был вполне способен.
    """
    from telegram.error import NetworkError

    monkeypatch.setattr(bot_module.config, "ADMIN_TELEGRAM_ID", 42, raising=False)
    bot = _Bot(fail=NetworkError("сеть недоступна"))

    await bot_module._set_command_menu(SimpleNamespace(bot=bot))


@pytest.mark.anyio
async def test_missing_admin_id_is_not_an_error(monkeypatch) -> None:
    monkeypatch.setattr(bot_module.config, "ADMIN_TELEGRAM_ID", None, raising=False)
    bot = _Bot()
    await bot_module._set_command_menu(SimpleNamespace(bot=bot))

    assert [scope for _, scope in bot.calls] == ["BotCommandScopeDefault"]


def test_admin_panel_button_appears_only_for_admin() -> None:
    """Панель существовала, но попасть в неё можно было только зная /admin."""
    from handlers.constants import build_workspace_inline_menu

    client_labels = [b.text for row in build_workspace_inline_menu() for b in row]
    admin_labels = [b.text for row in build_workspace_inline_menu(is_admin=True) for b in row]

    assert not any("Админ" in label for label in client_labels)
    assert admin_labels[0].endswith("Админ-панель")


def test_admin_button_reuses_the_existing_callback() -> None:
    """Кнопка ведёт в обработчик, который уже есть, — новой ветки не заводим."""
    from handlers.constants import build_workspace_inline_menu

    button = build_workspace_inline_menu(is_admin=True)[0][0]
    assert button.callback_data == "admin_panel"
