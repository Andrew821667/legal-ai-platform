"""Команды в кнопке меню и вход в рабочее место.

Раньше бот не задавал команды вовсе: кнопка меню была пуста, и об админ-панели
можно было узнать, только зная, что набрать «/admin».
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
        self.calls: list[tuple[int, str]] = []
        self.menu: list[tuple[int, str]] = []
        self._fail = fail

    async def set_my_commands(self, commands, scope=None):
        if self._fail is not None:
            raise self._fail
        self.calls.append((len(commands), type(scope).__name__))

    async def set_chat_menu_button(self, chat_id, menu_button):
        self.menu.append((chat_id, type(menu_button).__name__))


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
    await bot_module._set_command_menu(SimpleNamespace(bot=_Bot(fail=NetworkError("нет сети"))))


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


def test_workspace_button_opens_a_web_app() -> None:
    """Рабочее место — мини-апп, а не переписка в чате."""
    from handlers.constants import build_admin_panel_menu

    button = build_admin_panel_menu()[0][0]
    assert button.web_app is not None
    assert "Рабочее место" in button.text


def test_panel_survives_missing_workspace_url(monkeypatch) -> None:
    """Кнопка, ведущая в никуда, хуже её отсутствия."""
    import handlers.constants as constants

    monkeypatch.setattr(constants.get_config(), "LAWYER_WORKSPACE_URL", "", raising=False)

    labels = [b.text for row in constants.build_admin_panel_menu() for b in row]
    assert not any("Рабочее место" in label for label in labels)
    assert any("Лиды" in label for label in labels)


@pytest.mark.anyio
async def test_menu_button_stays_the_commands_list(monkeypatch) -> None:
    """Угловая кнопка меню — список команд, а не прямое открытие раздела.

    Раньше здесь стоял MenuButtonWebApp, и он забирал быстрый доступ к /admin
    и остальным командам ради одного касания до одного экрана. Широкий доступ
    к рабочему месту теперь на постоянной клавиатуре, а не здесь.
    """
    monkeypatch.setattr(bot_module.config, "ADMIN_TELEGRAM_ID", 42, raising=False)
    bot = _Bot()
    await bot_module._set_command_menu(SimpleNamespace(bot=bot))

    assert bot.menu == [(42, "MenuButtonDefault")]


@pytest.mark.anyio
async def test_menu_button_failure_does_not_block_startup(monkeypatch) -> None:
    from telegram.error import NetworkError

    monkeypatch.setattr(bot_module.config, "ADMIN_TELEGRAM_ID", 42, raising=False)

    class _Failing(_Bot):
        async def set_chat_menu_button(self, chat_id, menu_button):
            raise NetworkError("нет сети")

    await bot_module._set_command_menu(SimpleNamespace(bot=_Failing()))


def test_admin_reply_keyboard_has_workspace_on_its_own_row(monkeypatch) -> None:
    """Одиночная кнопка в reply-клавиатуре растягивается на весь ряд —
    ровно так рабочее место становится заметным без лишних касаний."""
    import handlers.constants as constants

    monkeypatch.setattr(
        constants.get_config(), "LAWYER_WORKSPACE_URL", "https://example.ru/lawyer", raising=False
    )
    rows = constants.build_admin_reply_menu()
    workspace_row = next(row for row in rows if any("Рабочее место" in b.text for b in row))
    assert len(workspace_row) == 1
    assert workspace_row[0].web_app is not None


def test_admin_reply_keyboard_hides_workspace_without_url(monkeypatch) -> None:
    import handlers.constants as constants

    monkeypatch.setattr(constants.get_config(), "LAWYER_WORKSPACE_URL", "", raising=False)
    labels = [b.text for row in constants.build_admin_reply_menu() for b in row]
    assert not any("Рабочее место" in label for label in labels)
    # Первый ряд остаётся на месте — новая кнопка ничего не вытесняет.
    assert any("Мини-апп" in label for label in labels)


def test_client_button_opens_the_miniapp_directly(monkeypatch) -> None:
    """Раньше нажатие слало текст, который потом разбирал роутер — теперь
    открывается сразу, без круга через отправку и разбор сообщения."""
    import handlers.constants as constants

    monkeypatch.setattr(
        constants.get_config(), "CLIENT_MINIAPP_URL", "https://example.ru/miniapp", raising=False
    )
    button = constants.client_miniapp_button()
    assert button.web_app is not None
    assert button.web_app.url == "https://example.ru/miniapp"


def test_client_button_falls_back_to_text_without_url(monkeypatch) -> None:
    """Этот ряд клавиатуры не может остаться пустым — в отличие от
    необязательных кнопок вроде рабочего места юриста."""
    import handlers.constants as constants

    monkeypatch.setattr(constants.get_config(), "CLIENT_MINIAPP_URL", "", raising=False)
    button = constants.client_miniapp_button()
    assert button.web_app is None
    assert button.text == "🧭 Рабочий стол"


def test_case_management_button_hidden_without_username(monkeypatch) -> None:
    """Имя того бота неизвестно на момент написания — кнопка не должна вести в никуда."""
    import handlers.constants as constants

    monkeypatch.setattr(
        constants.get_config(), "CASE_MANAGEMENT_BOT_USERNAME", "", raising=False
    )
    labels = [b.text for row in constants.build_admin_panel_menu() for b in row]
    assert not any("Судебные" in label for label in labels)


def test_case_management_button_appears_when_configured(monkeypatch) -> None:
    import handlers.constants as constants

    monkeypatch.setattr(
        constants.get_config(), "CASE_MANAGEMENT_BOT_USERNAME", "lawtable_bot", raising=False
    )
    rows = constants.build_admin_panel_menu()
    button = next(b for row in rows for b in row if "Судебные" in b.text)
    assert button.url == "https://t.me/lawtable_bot"
    # Пункт «Закрыть» остаётся последним — новая кнопка не должна его сдвигать в середину.
    assert rows[-1][0].callback_data == "admin_close"


def test_workspace_link_points_at_the_client(monkeypatch) -> None:
    """Из уведомления — сразу в карточку, а не в общий список."""
    import handlers.constants as constants

    monkeypatch.setattr(
        constants.get_config(), "LAWYER_WORKSPACE_URL", "https://example.ru/lawyer", raising=False
    )
    lead = "11111111-1111-4111-8111-111111111111"
    assert constants.lawyer_workspace_link(lead) == f"https://example.ru/lawyer?client={lead}"
    assert constants.lawyer_workspace_link() == "https://example.ru/lawyer"


def test_workspace_link_survives_a_query_in_the_base_url(monkeypatch) -> None:
    import handlers.constants as constants

    monkeypatch.setattr(
        constants.get_config(), "LAWYER_WORKSPACE_URL", "https://example.ru/lawyer?src=bot", raising=False
    )
    assert constants.lawyer_workspace_link("abc") == "https://example.ru/lawyer?src=bot&client=abc"


def test_workspace_row_is_empty_without_an_address(monkeypatch) -> None:
    """Кнопка, ведущая в никуда, хуже её отсутствия — ряд просто не добавляется."""
    import handlers.constants as constants

    monkeypatch.setattr(constants.get_config(), "LAWYER_WORKSPACE_URL", "", raising=False)
    assert constants.workspace_row("abc") == []
    assert constants.lawyer_workspace_link("abc") == ""


def test_workspace_row_without_lead_opens_the_list(monkeypatch) -> None:
    """Если клиент неизвестен, кнопка всё равно полезна — ведёт в список."""
    import handlers.constants as constants

    monkeypatch.setattr(
        constants.get_config(), "LAWYER_WORKSPACE_URL", "https://example.ru/lawyer", raising=False
    )
    (row,) = constants.workspace_row(None)
    assert row[0].web_app.url == "https://example.ru/lawyer"
