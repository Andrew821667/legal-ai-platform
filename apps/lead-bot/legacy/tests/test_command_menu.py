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


def test_admin_reply_keyboard_is_a_single_workspace_button(monkeypatch) -> None:
    """Одна кнопка на всю ширину — там, где у клиента «Рабочий стол».

    Второй ряд с клиентским мини-аппом закрывал низ экрана, а владельцу он
    не нужен: клавиатура в один ряд не закрывает ничего.
    """
    import handlers.constants as constants

    monkeypatch.setattr(
        constants.get_config(), "LAWYER_WORKSPACE_URL", "https://example.ru/lawyer", raising=False
    )
    rows = constants.build_admin_reply_menu()
    assert len(rows) == 1 and len(rows[0]) == 1
    button = rows[0][0]
    assert "Рабочее пространство" in button.text
    assert button.web_app is not None and button.web_app.url == "https://example.ru/lawyer"


def test_admin_reply_keyboard_falls_back_to_client_menu_without_url(monkeypatch) -> None:
    """Ряд не может остаться пустым — без адреса владелец видит то же, что клиент."""
    import handlers.constants as constants

    monkeypatch.setattr(constants.get_config(), "LAWYER_WORKSPACE_URL", "", raising=False)
    labels = [b.text for row in constants.build_admin_reply_menu() for b in row]
    assert not any("Рабочее пространство" in label for label in labels)
    assert any("Мини-апп" in label for label in labels)


def test_client_button_is_text() -> None:
    """Mini App из кнопки reply-клавиатуры получает пустой initData — так
    устроен Telegram. Поэтому кнопка текстовая: бот отвечает inline-кнопкой,
    а уже она открывает мини-апп с полноценным входом."""
    import handlers.constants as constants
    from handlers.user_routing import _is_navigation_shortcut

    button = constants.client_miniapp_button()
    assert button.web_app is None
    assert button.text == "📱 Мини-апп"
    # Навигация, а не запрос клиента: первое сообщение новичка с этой кнопки
    # не должно уйти в разбор лида.
    assert _is_navigation_shortcut("📱 Мини-апп")
    assert _is_navigation_shortcut("🧭 Рабочий стол")  # старая надпись на старых клавиатурах


def _static_reply_call(text: str, sent: list, *, menu_calls: list):
    from handlers.user_routing import maybe_handle_static_reply_action

    async def reply_text(message_text, reply_markup=None, **kwargs):
        sent.append((message_text, reply_markup))

    async def menu_handler(update, context):
        menu_calls.append(text)

    async def unexpected(update, context):  # pragma: no cover - страховка
        raise AssertionError("не та ветка")

    return maybe_handle_static_reply_action(
        update=SimpleNamespace(),
        context=SimpleNamespace(),
        original_message=SimpleNamespace(reply_text=reply_text),
        message_text=text,
        user=SimpleNamespace(id=7),
        user_data={"id": 1},
        consent_state={},
        is_admin=False,
        allow_lead_processing=True,
        consultation_requires_pdn=False,
        menu_handler=menu_handler,
        profile_handler=unexpected,
        documents_handler=unexpected,
        reset_handler=unexpected,
    )


@pytest.mark.anyio
async def test_client_button_answers_with_an_inline_miniapp_button(monkeypatch) -> None:
    """Одно касание длиннее — зато мини-апп открывается с полноценным входом."""
    import handlers.constants as constants

    monkeypatch.setattr(
        constants.get_config(), "CLIENT_MINIAPP_URL", "https://example.ru/miniapp", raising=False
    )
    sent: list = []
    menu_calls: list = []
    assert await _static_reply_call("📱 Мини-апп", sent, menu_calls=menu_calls)

    assert menu_calls == []
    ((_, markup),) = sent
    (button,) = [b for row in markup.inline_keyboard for b in row]
    assert button.web_app is not None and button.web_app.url == "https://example.ru/miniapp"


@pytest.mark.anyio
async def test_client_button_without_an_address_opens_the_menu(monkeypatch) -> None:
    """Кнопка, ведущая в никуда, хуже её отсутствия — тогда обычное меню."""
    import handlers.constants as constants

    monkeypatch.setattr(constants.get_config(), "CLIENT_MINIAPP_URL", "", raising=False)
    sent: list = []
    menu_calls: list = []
    assert await _static_reply_call("📱 Мини-апп", sent, menu_calls=menu_calls)

    assert sent == []
    assert menu_calls == ["📱 Мини-апп"]


def test_admin_bottom_button_carries_a_login_token(monkeypatch) -> None:
    """Нижняя кнопка не может войти по initData — Telegram его не передаёт.
    Поэтому она ведёт на /lawyer/login с тем же токеном, что «Ссылка для Safari»."""
    import handlers.constants as constants

    cfg = constants.get_config()
    monkeypatch.setattr(cfg, "LAWYER_WORKSPACE_URL", "https://example.ru/lawyer", raising=False)
    monkeypatch.setattr(cfg, "LAWYER_SESSION_SECRET", "s3cret", raising=False)
    monkeypatch.setattr(cfg, "ADMIN_TELEGRAM_ID", 42, raising=False)

    url = constants.build_admin_reply_menu()[0][0].web_app.url
    assert url.startswith("https://example.ru/lawyer/login?token=42.")

    # Токен настоящий: подпись пересчитывается тем же способом, что и в вебе.
    import hashlib
    import hmac

    token = url.split("token=", 1)[1]
    user_id, issued_at, signature = token.split(".")
    assert user_id == "42"
    expected = hmac.new(b"s3cret", f"{user_id}.{issued_at}".encode(), hashlib.sha256).hexdigest()
    assert signature == expected


def test_admin_bottom_button_without_secret_is_a_plain_link(monkeypatch) -> None:
    """Без секрета выпускать токен нечем — тогда голый адрес, и рабочее место
    само объяснит, что делать."""
    import handlers.constants as constants

    cfg = constants.get_config()
    monkeypatch.setattr(cfg, "LAWYER_WORKSPACE_URL", "https://example.ru/lawyer", raising=False)
    monkeypatch.setattr(cfg, "LAWYER_SESSION_SECRET", "", raising=False)
    assert constants.build_admin_reply_menu()[0][0].web_app.url == "https://example.ru/lawyer"


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


@pytest.mark.anyio
async def test_admin_panel_brings_the_bottom_button(monkeypatch) -> None:
    """Владелец заходит в /admin чаще, чем в /start — клавиатура должна прийти и отсюда."""
    from telegram import ReplyKeyboardMarkup

    import handlers.admin as admin
    import handlers.constants as constants

    monkeypatch.setattr(admin.config, "ADMIN_TELEGRAM_ID", 42, raising=False)
    monkeypatch.setattr(
        constants.get_config(), "LAWYER_WORKSPACE_URL", "https://example.ru/lawyer", raising=False
    )
    sent: list[tuple[str, object]] = []

    async def reply_text(text, reply_markup=None, **kwargs):
        sent.append((text, reply_markup))

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        message=SimpleNamespace(reply_text=reply_text),
    )
    await admin.show_admin_panel(update, SimpleNamespace())

    assert len(sent) == 2
    assert "АДМИН-ПАНЕЛЬ" in sent[0][0]
    keyboard = sent[1][1]
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    labels = [b.text for row in keyboard.keyboard for b in row]
    assert labels == ["🗂 Рабочее пространство"]
