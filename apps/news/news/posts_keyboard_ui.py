from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


InlineButtonFactory = Callable[..., Any]
SubmenuRowsFactory = Callable[..., list[list[Any]]]


def build_posts_keyboard_rows(
    *,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    status: str,
    page_size: int,
    status_badge: Callable[[str], str],
    publication_kind_badge: Callable[[str], str],
    row_publication_kind: Callable[[dict[str, Any]], str],
    callback_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    buttons: list[list[Any]] = []
    for idx, row in enumerate(rows, start=offset + 1):
        post_id = str(row.get("id"))
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        row_status = str(row.get("status") or status)
        publication_kind = row_publication_kind(row)
        buttons.append(
            [
                callback_button(
                    f"{idx}. {status_badge(row_status)} {publication_kind_badge(publication_kind)} {title[:40]}",
                    callback_data=f"pv:{post_id}:{status}:{offset}",
                )
            ]
        )

    if rows and status == "draft":
        buttons.append([callback_button("🟡 На проверку (все на странице)", callback_data=f"ba:review:{status}:{offset}")])
    if rows and status in {"review", "failed"}:
        buttons.append([callback_button("✅ В готовые (все на странице)", callback_data=f"ba:ready:{status}:{offset}")])
    if rows and status == "ready":
        buttons.append([callback_button("🗓 На публикацию (все на странице)", callback_data=f"ba:schedule:{status}:{offset}")])

    nav: list[Any] = []
    prev_offset = max(0, offset - page_size)
    next_offset = offset + page_size
    if offset > 0:
        nav.append(callback_button("⬅️ Назад", callback_data=f"pl:{status}:{prev_offset}"))
    if next_offset < total:
        nav.append(callback_button("➡️ Далее", callback_data=f"pl:{status}:{next_offset}"))
    if nav:
        buttons.append(nav)

    buttons.append([callback_button("🔄 Обновить список", callback_data=f"pl:{status}:{offset}")])
    buttons.extend(submenu_nav_rows(back_callback="sec:worklists", back_label="🔙 К рабочим спискам"))
    return buttons


def build_review_posts_keyboard_rows(
    *,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    review_filter: str,
    kind_filter: str,
    theme_filter: str,
    page_size: int,
    pillar_keys: Sequence[str],
    pillar_display: Callable[[str], str],
    review_origin_badge: Callable[[str], str],
    publication_kind_badge: Callable[[str], str],
    row_publication_kind: Callable[[dict[str, Any]], str],
    inline_button: InlineButtonFactory,
    callback_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    buttons: list[list[Any]] = [
        [
            inline_button(f"{'• ' if review_filter == 'all' else ''}Все", callback_data=f"rv:all:{kind_filter}:{theme_filter}:0"),
            inline_button(f"{'• ' if review_filter == 'ai' else ''}AI", callback_data=f"rv:ai:{kind_filter}:{theme_filter}:0"),
            inline_button(f"{'• ' if review_filter == 'manual' else ''}Ручные", callback_data=f"rv:manual:{kind_filter}:{theme_filter}:0"),
        ]
    ]

    kind_rows = [
        ("all", "Все виды"),
        ("daily", "Ежедневные"),
        ("weekly_review", "Обзоры"),
        ("longread", "Лонгриды"),
        ("practice", "Практика недели"),
        ("other", "Прочее"),
    ]
    for index in range(0, len(kind_rows), 2):
        chunk = kind_rows[index : index + 2]
        buttons.append(
            [
                inline_button(
                    f"{'• ' if kind_filter == item_key else ''}{item_label}",
                    callback_data=f"rv:{review_filter}:{item_key}:{theme_filter}:0",
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
                    callback_data=f"rv:{review_filter}:{kind_filter}:{item_key}:0",
                )
                for item_key, item_label in chunk
            ]
        )

    for idx, row in enumerate(rows, start=offset + 1):
        post_id = str(row.get("id"))
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        publication_kind = row_publication_kind(row)
        buttons.append(
            [
                callback_button(
                    f"{idx}. {review_origin_badge(str(row.get('format_type') or ''))} {publication_kind_badge(publication_kind)} {title[:38]}",
                    callback_data=f"pv:{post_id}:review:{offset}",
                )
            ]
        )

    buttons.append([callback_button("✅ В готовые (все на странице)", callback_data=f"ba:ready:review:{offset}")])

    nav: list[Any] = []
    prev_offset = max(0, offset - page_size)
    next_offset = offset + page_size
    if offset > 0:
        nav.append(callback_button("⬅️ Назад", callback_data=f"rv:{review_filter}:{kind_filter}:{theme_filter}:{prev_offset}"))
    if next_offset < total:
        nav.append(callback_button("➡️ Далее", callback_data=f"rv:{review_filter}:{kind_filter}:{theme_filter}:{next_offset}"))
    if nav:
        buttons.append(nav)

    buttons.append([callback_button("🔄 Обновить список", callback_data=f"rv:{review_filter}:{kind_filter}:{theme_filter}:{offset}")])
    buttons.extend(submenu_nav_rows(back_callback="sec:worklists", back_label="🔙 К рабочим спискам"))
    return buttons
