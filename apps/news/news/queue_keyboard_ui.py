from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


InlineButtonFactory = Callable[..., Any]
SubmenuRowsFactory = Callable[..., list[list[Any]]]


def build_auto_queue_keyboard_rows(
    *,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    queue_filter: str,
    theme_filter: str,
    page_size: int,
    pillar_keys: Sequence[str],
    pillar_display: Callable[[str], str],
    publication_kind_badge: Callable[[str], str],
    row_publication_kind: Callable[[dict[str, Any]], str],
    auto_queue_context: Callable[[str, str], str],
    inline_button: InlineButtonFactory,
    callback_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    buttons: list[list[Any]] = []
    filter_rows = [
        ("all", "Все"),
        ("daily", "Ежедневные"),
        ("weekly_review", "Обзоры"),
        ("longread", "Лонгриды"),
        ("humor", "Практика недели"),
        ("other", "Прочее"),
    ]
    for index in range(0, len(filter_rows), 2):
        chunk = filter_rows[index : index + 2]
        buttons.append(
            [
                inline_button(
                    f"{'• ' if queue_filter == item_key else ''}{item_label}",
                    callback_data=f"aq:{item_key}:{theme_filter}:0",
                )
                for item_key, item_label in chunk
            ]
        )

    theme_rows = [("all", "Все темы")] + [(pillar, pillar_display(pillar)) for pillar in pillar_keys]
    for index in range(0, len(theme_rows), 2):
        chunk = theme_rows[index : index + 2]
        buttons.append(
            [
                inline_button(
                    f"{'• ' if theme_filter == item_key else ''}{item_label}",
                    callback_data=f"aq:{queue_filter}:{item_key}:0",
                )
                for item_key, item_label in chunk
            ]
        )

    for idx, row in enumerate(rows, start=offset + 1):
        post_id = str(row.get("id"))
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        kind = row_publication_kind(row)
        buttons.append(
            [
                callback_button(
                    f"{idx}. {publication_kind_badge(kind)} {title[:40]}",
                    callback_data=f"pv:{post_id}:{auto_queue_context(queue_filter, theme_filter)}:{offset}",
                )
            ]
        )

    nav: list[Any] = []
    prev_offset = max(0, offset - page_size)
    next_offset = offset + page_size
    if offset > 0:
        nav.append(callback_button("⬅️ Назад", callback_data=f"aq:{queue_filter}:{theme_filter}:{prev_offset}"))
    if next_offset < total:
        nav.append(callback_button("➡️ Далее", callback_data=f"aq:{queue_filter}:{theme_filter}:{next_offset}"))
    if nav:
        buttons.append(nav)

    buttons.append(
        [
            inline_button("🗓 Календарь", callback_data="cal:summary"),
            inline_button("🕒 Время слотов", callback_data="sch:menu"),
        ]
    )
    buttons.append(
        [
            inline_button("⏱ Ритм", callback_data="int:menu"),
            inline_button("🔄 Обновить", callback_data=f"aq:{queue_filter}:{theme_filter}:{offset}"),
        ]
    )
    buttons.extend(submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
    return buttons


def build_manual_queue_keyboard_rows(
    *,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    queue_filter: str,
    theme_filter: str,
    page_size: int,
    pillar_keys: Sequence[str],
    pillar_display: Callable[[str], str],
    queue_context: Callable[[str, str], str],
    publication_kind_badge: Callable[[str], str],
    row_publication_kind: Callable[[dict[str, Any]], str],
    inline_button: InlineButtonFactory,
    callback_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    buttons: list[list[Any]] = [
        [
            callback_button("⚡ К публикации сейчас", callback_data=f"mq:due:{theme_filter}:0"),
            callback_button("📚 Все готовые", callback_data=f"mq:all:{theme_filter}:0"),
        ]
    ]

    theme_rows = [("all", "Все темы")] + [(pillar, pillar_display(pillar)) for pillar in pillar_keys]
    for index in range(0, len(theme_rows), 2):
        chunk = theme_rows[index : index + 2]
        buttons.append(
            [
                inline_button(
                    f"{'• ' if theme_filter == item_key else ''}{item_label}",
                    callback_data=f"mq:{queue_filter}:{item_key}:0",
                )
                for item_key, item_label in chunk
            ]
        )

    context = queue_context(queue_filter, theme_filter)
    for idx, row in enumerate(rows, start=offset + 1):
        post_id = str(row.get("id"))
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        publication_kind = row_publication_kind(row)
        buttons.append(
            [
                callback_button(
                    f"{idx}. {publication_kind_badge(publication_kind)} {title[:40]}",
                    callback_data=f"pv:{post_id}:{context}:{offset}",
                )
            ]
        )

    if rows:
        if queue_filter == "due":
            buttons.append(
                [
                    callback_button("🚀 Страница", callback_data=f"mbp:{queue_filter}:{offset}:page"),
                    callback_button("⚡ Топ-3", callback_data=f"mbp:{queue_filter}:{offset}:top3"),
                    callback_button("🔥 Топ-5", callback_data=f"mbp:{queue_filter}:{offset}:top5"),
                ]
            )
        else:
            buttons.append([callback_button("🚀 Опубликовать страницу", callback_data=f"mbp:{queue_filter}:{offset}:page")])

    nav: list[Any] = []
    prev_offset = max(0, offset - page_size)
    next_offset = offset + page_size
    if offset > 0:
        nav.append(callback_button("⬅️ Назад", callback_data=f"mq:{queue_filter}:{theme_filter}:{prev_offset}"))
    if next_offset < total:
        nav.append(callback_button("➡️ Далее", callback_data=f"mq:{queue_filter}:{theme_filter}:{next_offset}"))
    if nav:
        buttons.append(nav)

    buttons.append([callback_button("🔄 Обновить очередь", callback_data=f"mq:{queue_filter}:{theme_filter}:{offset}")])
    buttons.extend(submenu_nav_rows(back_callback="sec:worklists", back_label="🔙 К рабочим спискам"))
    return buttons
