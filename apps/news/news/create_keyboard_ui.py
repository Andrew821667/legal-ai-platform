from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


InlineButtonFactory = Callable[..., Any]
TwoColumnRowsFactory = Callable[[list[Any]], list[list[Any]]]
SubmenuRowsFactory = Callable[..., list[list[Any]]]


def build_create_start_keyboard_rows(
    *,
    two_column_rows: TwoColumnRowsFactory,
    callback_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    rows = two_column_rows(
        [
            callback_button("✍️ Написать вручную", callback_data="cn:manual"),
            callback_button("🤖 По тезисам", callback_data="cn:ai"),
            callback_button("🎙 Из транскриба / voice", callback_data="cn:transcript"),
        ]
    )
    rows.extend(submenu_nav_rows(back_callback="cn:cancel"))
    return rows


def build_create_kind_keyboard_rows(
    *,
    post_kind_order: Sequence[str],
    post_kind_label: Callable[[str], str],
    two_column_rows: TwoColumnRowsFactory,
    callback_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    rows = two_column_rows(
        [callback_button(post_kind_label(kind), callback_data=f"ck:{kind}") for kind in post_kind_order]
    )
    rows.extend(submenu_nav_rows(back_callback="cn:cancel"))
    return rows


def build_create_theme_keyboard_rows(
    *,
    theme_order: Sequence[str],
    theme_label: Callable[[str], str],
    two_column_rows: TwoColumnRowsFactory,
    callback_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    rows = two_column_rows([callback_button(theme_label(theme), callback_data=f"ct:{theme}") for theme in theme_order])
    rows.extend(submenu_nav_rows(back_callback="cn:cancel"))
    return rows


def build_create_media_keyboard_rows(
    *,
    can_clear: bool = False,
    media_count: int = 0,
    editing: bool = False,
    callback_button: InlineButtonFactory,
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    if media_count > 0:
        rows.append([callback_button(f"✅ Готово ({media_count})", callback_data="cm:done")])
    elif not editing:
        rows.append([callback_button("⏭ Без медиа", callback_data="cm:skip")])
    else:
        rows.append([callback_button("✅ Готово", callback_data="cm:done")])

    if can_clear:
        rows.insert(0, [callback_button("🗑 Убрать медиа", callback_data="cm:clear")])

    rows.append(
        [
            callback_button("🔙 Назад", callback_data="cn:cancel"),
            callback_button("🏠 Рабочий стол", callback_data="refresh"),
        ]
    )
    return rows


def build_create_link_keyboard_rows(
    *,
    can_clear: bool = False,
    cancel_callback: str = "cn:cancel",
    callback_button: InlineButtonFactory,
) -> list[list[Any]]:
    rows = [[callback_button("⏭ Без ссылки", callback_data="cl:skip")]]
    if can_clear:
        rows.insert(0, [callback_button("🗑 Убрать ссылку", callback_data="cl:clear")])
    rows.append(
        [
            callback_button("🔙 Назад", callback_data=cancel_callback),
            callback_button("🏠 Рабочий стол", callback_data="refresh"),
        ]
    )
    return rows


def build_create_draft_keyboard_rows(
    *,
    callback_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    rows: list[list[Any]] = [
        [
            callback_button("🧱 Тип", callback_data="ce:kind"),
            callback_button("🧭 Тема", callback_data="ce:theme"),
        ],
        [
            callback_button("🖼 Медиа", callback_data="ce:media"),
            callback_button("🔗 Ссылка", callback_data="ce:link"),
        ],
        [
            callback_button("🗂 Материал", callback_data="ce:source"),
            callback_button("✏️ Заголовок", callback_data="ce:title"),
        ],
        [callback_button("📝 Текст", callback_data="ce:text")],
        [callback_button("🤖 Доработать через LLM", callback_data="ce:ai")],
        [callback_button("🆕 Сохранить в черновики", callback_data="cs:draft")],
        [callback_button("🟡 Отправить на проверку", callback_data="cs:review")],
        [
            callback_button("✅ +1ч", callback_data="cs:scheduled:h1"),
            callback_button("🌙 19:00", callback_data="cs:scheduled:e19"),
        ],
        [callback_button("🌤 Завтра 10:00", callback_data="cs:scheduled:t10")],
        [
            callback_button("⤴️ Последнее в начало", callback_data="cr:lastfirst"),
            callback_button("🔄 Развернуть медиа", callback_data="cr:reverse"),
        ],
        [callback_button("🧹 Новый с нуля", callback_data="cn:start")],
    ]
    rows.extend(submenu_nav_rows(back_callback="cn:start"))
    return rows
