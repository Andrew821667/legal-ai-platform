from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any


InlineButtonFactory = Callable[..., Any]
SubmenuRowsFactory = Callable[..., list[list[Any]]]
TwoColumnRowsFactory = Callable[[list[Any]], list[list[Any]]]


def build_themes_keyboard_rows(
    *,
    counts: Mapping[str, int],
    generation_themes_total: int,
    enabled_generation_themes_count: int,
    active_longread_topics_count: int,
    longread_topics_total: int,
    inline_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    total_archive = sum(max(0, int(value)) for value in counts.values())
    rows: list[list[Any]] = [
        [
            inline_button(
                f"🗞 Ежедневные ({enabled_generation_themes_count}/{generation_themes_total})",
                callback_data="thm:daily",
            ),
            inline_button(
                f"📚 Лонгриды ({active_longread_topics_count}/{longread_topics_total})",
                callback_data="lt:menu",
            ),
        ],
        [
            inline_button(f"🗂 Архив ({total_archive})", callback_data="thm:archive"),
            inline_button("⚙️ Генерация", callback_data="sec:generate"),
        ],
    ]
    rows.extend(submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
    return rows


def build_themes_daily_keyboard_rows(
    *,
    generation_theme_keys: Sequence[str],
    generation_theme_counts: Mapping[str, int],
    enabled_generation_themes: set[str],
    generation_theme_label: Callable[[str], str],
    inline_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    rows: list[list[Any]] = [
        [
            inline_button("✅ Включить все", callback_data="gt:bulk:on"),
            inline_button("⚖️ Профиль канала", callback_data="gt:bulk:profile"),
        ]
    ]
    for theme_key in generation_theme_keys:
        rows.append(
            [
                inline_button(
                    f"{'✅' if theme_key in enabled_generation_themes else '☐'} {generation_theme_label(theme_key)} ({generation_theme_counts.get(theme_key, 0)})"[
                        :56
                    ],
                    callback_data=f"gt:{theme_key}",
                )
            ]
        )
    rows.append([inline_button("📚 Открыть темы лонгридов", callback_data="lt:menu")])
    rows.extend(submenu_nav_rows(back_callback="sec:themes", back_label="🔙 К блокам тематик"))
    return rows


def build_themes_archive_keyboard_rows(
    *,
    pillar_keys: Sequence[str],
    counts: Mapping[str, int],
    pillar_display: Callable[[str], str],
    inline_button: InlineButtonFactory,
    two_column_rows: TwoColumnRowsFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    rows = two_column_rows(
        [
            inline_button(f"{pillar_display(pillar)} ({counts.get(pillar, 0)})"[:40], callback_data=f"th:{pillar}:0")
            for pillar in pillar_keys
        ]
    )
    rows.extend(submenu_nav_rows(back_callback="sec:themes", back_label="🔙 К блокам тематик"))
    return rows


def build_theme_posts_keyboard_rows(
    *,
    pillar: str,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    page_size: int,
    status_badge: Callable[[str], str],
    publication_kind_badge: Callable[[str], str],
    publication_kind_resolver: Callable[[dict[str, Any]], str],
    callback_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    buttons: list[list[Any]] = []
    for idx, row in enumerate(rows, start=offset + 1):
        post_id = str(row.get("id"))
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        status = str(row.get("status") or "scheduled")
        publication_kind = publication_kind_resolver(row)
        buttons.append(
            [
                callback_button(
                    f"{idx}. {status_badge(status)} {publication_kind_badge(publication_kind)} {title[:40]}",
                    callback_data=f"pv:{post_id}:th_{pillar}:{offset}",
                )
            ]
        )

    nav: list[Any] = []
    prev_offset = max(0, offset - page_size)
    next_offset = offset + page_size
    if offset > 0:
        nav.append(callback_button("⬅️ Назад", callback_data=f"th:{pillar}:{prev_offset}"))
    if next_offset < total:
        nav.append(callback_button("➡️ Далее", callback_data=f"th:{pillar}:{next_offset}"))
    if nav:
        buttons.append(nav)

    buttons.extend(submenu_nav_rows(back_callback="sec:themes", back_label="🔙 К тематикам"))
    return buttons
