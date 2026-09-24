"""Второй аккаунт владельца: права владельца, но клиентский путь — как у клиента."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from telegram import InlineKeyboardButton

import bot as bot_module
from admin_access import is_admin_user, is_extra_admin
from handlers import markup

OWNER, SECOND, CLIENT = 61, 279, 500
CONFIG = SimpleNamespace(ADMIN_TELEGRAM_ID=OWNER, LAWYER_TELEGRAM_IDS=[SECOND])


def test_both_accounts_have_owner_rights_only_the_second_is_extra() -> None:
    assert is_admin_user(CONFIG, OWNER)
    assert is_admin_user(CONFIG, SECOND)
    assert not is_admin_user(CONFIG, CLIENT)
    assert not is_admin_user(CONFIG, None)
    assert is_extra_admin(CONFIG, SECOND)
    assert not is_extra_admin(CONFIG, OWNER)
    # Старый конфиг без списка — только основной аккаунт.
    assert not is_admin_user(SimpleNamespace(ADMIN_TELEGRAM_ID=OWNER), SECOND)


def test_config_reads_the_extra_accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import Config

    monkeypatch.setenv("ADMIN_TELEGRAM_ID", str(OWNER))
    monkeypatch.setenv("LAWYER_TELEGRAM_IDS", f" {SECOND}, {OWNER}, мусор,")
    assert Config().LAWYER_TELEGRAM_IDS == [SECOND]


def test_second_account_gets_both_the_workspace_and_the_client_buttons(monkeypatch) -> None:
    captured: dict = {}

    def admin_menu(user_id=None, *, client_too=False):
        captured.update(user_id=user_id, client_too=client_too)
        return [["рабочее"]]

    monkeypatch.setattr(markup, "config", CONFIG)
    monkeypatch.setattr(markup, "build_admin_reply_menu", admin_menu)
    markup.main_menu_markup(SECOND)
    # Токен входа — на сам второй аккаунт, и клиентская кнопка рядом.
    assert captured == {"user_id": SECOND, "client_too": True}
    markup.main_menu_markup(OWNER)
    assert captured == {"user_id": OWNER, "client_too": False}
    assert markup.main_menu_hint(SECOND) == "🗂"


def test_start_menu_for_the_second_account_keeps_the_client_miniapp(monkeypatch) -> None:
    workspace = InlineKeyboardButton("🗂 Рабочее место", callback_data="ws")
    miniapp = [[InlineKeyboardButton("📱 Мини-апп", callback_data="app")]]
    monkeypatch.setattr(markup, "lawyer_workspace_button", lambda *a, **k: workspace)
    monkeypatch.setattr(markup, "client_miniapp_inline_row", lambda: miniapp)

    def texts(kb):
        return [button.text for row in kb.inline_keyboard for button in row]

    second = texts(markup.start_markup_for(is_admin=True, client_too=True))
    assert "🗂 Рабочее место" in second and "📱 Мини-апп" in second
    owner = texts(markup.start_markup_for(is_admin=True))
    assert "🗂 Рабочее место" in owner and "📱 Мини-апп" not in owner
    client = texts(markup.start_markup_for())
    assert "📱 Мини-апп" in client and "🗂 Рабочее место" not in client


@pytest.mark.anyio
async def test_second_account_sees_the_admin_commands(monkeypatch) -> None:
    chats: list[int] = []

    class _Bot:
        async def set_my_commands(self, commands, scope=None):
            if type(scope).__name__ == "BotCommandScopeChat":
                chats.append(scope.chat_id)

        async def set_chat_menu_button(self, chat_id, menu_button):
            return None

    monkeypatch.setattr(bot_module.config, "ADMIN_TELEGRAM_ID", OWNER, raising=False)
    monkeypatch.setattr(bot_module.config, "LAWYER_TELEGRAM_IDS", [SECOND], raising=False)
    await bot_module._set_command_menu(SimpleNamespace(bot=_Bot()))
    assert chats == [OWNER, SECOND]
