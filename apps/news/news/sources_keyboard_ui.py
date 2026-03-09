from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any


InlineButtonFactory = Callable[..., Any]
UrlButtonFactory = Callable[[str, str], Any]
SubmenuRowsFactory = Callable[..., list[list[Any]]]


def _spec_value(spec: Any, field: str, default: Any = None) -> Any:
    if spec is None:
        return default
    if isinstance(spec, dict):
        return spec.get(field, default)
    return getattr(spec, field, default)


def build_sources_keyboard_rows(
    *,
    specs: Sequence[Any],
    page: int = 0,
    page_size: int = 12,
    inline_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    total_pages = max(1, (len(specs) + page_size - 1) // page_size)
    safe_page = max(0, min(page, total_pages - 1))
    start = safe_page * page_size
    chunk = specs[start : start + page_size]

    rows.append(
        [
            inline_button("📣 Telegram-каналы", callback_data="srd:telegram_channels"),
            inline_button("🔄 Обновить", callback_data=f"srcm:{safe_page}"),
        ]
    )

    for index in range(0, len(chunk), 2):
        pair = chunk[index : index + 2]
        rows.append(
            [
                inline_button(
                    str(_spec_value(spec, "name", ""))[:20],
                    callback_data=f"srd:{_spec_value(spec, 'key', '')}",
                )
                for spec in pair
            ]
        )

    nav: list[Any] = []
    if safe_page > 0:
        nav.append(inline_button("⬅️ Стр. назад", callback_data=f"srcm:{safe_page - 1}"))
    if safe_page + 1 < total_pages:
        nav.append(inline_button("➡️ Стр. далее", callback_data=f"srcm:{safe_page + 1}"))
    if nav:
        rows.append(nav)

    rows.append(
        [
            inline_button("⚙️ Генерация", callback_data="sec:generate"),
            inline_button("🧭 Тематики", callback_data="sec:themes"),
        ]
    )
    rows.extend(submenu_nav_rows(back_callback="refresh", back_label="🔙 Назад"))
    return rows


def build_source_detail_keyboard_rows(
    *,
    source_key: str,
    spec: Any | None,
    enabled: bool,
    telegram_channels: Sequence[str] | None = None,
    telegram_channel_enabled_map: Mapping[str, bool] | None = None,
    telegram_channel_group: Callable[[str], str] | None = None,
    telegram_channel_group_label: Callable[[str], str] | None = None,
    telegram_channel_slug: Callable[[str], str] | None = None,
    telegram_channel_label: Callable[[str], str] | None = None,
    inline_button: InlineButtonFactory,
    submenu_nav_rows: SubmenuRowsFactory,
    button_style_success: str | None = "success",
) -> list[list[Any]]:
    rows: list[list[Any]] = [
        [
            inline_button(
                "☐ Выключить" if enabled else "✅ Включить",
                callback_data=f"srt:{source_key}",
                style=button_style_success if not enabled else None,
            )
        ]
    ]

    integrated = bool(_spec_value(spec, "integrated", False))
    if integrated:
        rows.append([inline_button("📄 Посты по источнику", callback_data=f"src:{source_key}:0")])

    if source_key == "telegram_channels":
        channels = list(telegram_channels or [])
        enabled_map = telegram_channel_enabled_map or {}
        group_fn = telegram_channel_group or (lambda _value: "legal")
        group_label_fn = telegram_channel_group_label or (lambda value: value)
        slug_fn = telegram_channel_slug or (lambda value: str(value).strip().lower().removeprefix("@"))
        channel_label_fn = telegram_channel_label or (lambda value: str(value).strip())
        for group in ("legal", "ai"):
            group_channels = [channel for channel in channels if group_fn(channel) == group]
            if not group_channels:
                continue
            rows.append([inline_button(group_label_fn(group), callback_data="noop")])
            for index in range(0, len(group_channels), 2):
                pair = group_channels[index : index + 2]
                rows.append(
                    [
                        inline_button(
                            f"{'✅' if enabled_map.get(slug_fn(item), True) else '☐'} {channel_label_fn(item)}",
                            callback_data=f"stc:{slug_fn(item)}",
                        )
                        for item in pair
                    ]
                )

    rows.extend(submenu_nav_rows(back_callback="sec:sources", back_label="🔙 К источникам"))
    return rows


def build_telegram_channel_detail_keyboard_rows(
    *,
    slug: str,
    enabled: bool,
    inline_button: InlineButtonFactory,
    url_button: UrlButtonFactory,
    button_style_success: str | None = "success",
) -> list[list[Any]]:
    normalized = str(slug).strip().lower().removeprefix("@")
    return [
        [
            inline_button(
                "☐ Выключить" if enabled else "✅ Включить",
                callback_data=f"scc:{normalized}",
                style=button_style_success if not enabled else None,
            )
        ],
        [url_button("🔗 Открыть канал", f"https://t.me/{normalized}")],
        [
            inline_button("🔙 К Telegram Channels", callback_data="srd:telegram_channels"),
            inline_button("🏠 Рабочий стол", callback_data="refresh"),
        ],
    ]


def build_source_posts_keyboard_rows(
    *,
    source_key: str,
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
                    callback_data=f"pv:{post_id}:src_{source_key}:{offset}",
                )
            ]
        )

    nav: list[Any] = []
    prev_offset = max(0, offset - page_size)
    next_offset = offset + page_size
    if offset > 0:
        nav.append(callback_button("⬅️ Назад", callback_data=f"src:{source_key}:{prev_offset}"))
    if next_offset < total:
        nav.append(callback_button("➡️ Далее", callback_data=f"src:{source_key}:{next_offset}"))
    if nav:
        buttons.append(nav)

    buttons.extend(submenu_nav_rows(back_callback="sec:sources", back_label="🔙 К источникам"))
    return buttons
