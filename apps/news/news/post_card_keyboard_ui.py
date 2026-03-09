from __future__ import annotations

from collections.abc import Callable
from typing import Any


InlineButtonFactory = Callable[..., Any]
TwoColumnRowsFactory = Callable[[list[Any]], list[list[Any]]]


def build_post_card_keyboard_rows(
    *,
    post_id: str,
    status: str,
    offset: int,
    two_column_rows: TwoColumnRowsFactory,
    callback_button: InlineButtonFactory,
    is_auto_queue_context: Callable[[str], bool],
    auto_queue_filters_from_context: Callable[[str], tuple[str, str]],
    is_calendar_context: Callable[[str], bool],
    calendar_date_from_context: Callable[[str], str],
    is_theme_context: Callable[[str], bool],
    theme_from_context: Callable[[str], str],
    is_source_context: Callable[[str], bool],
    source_from_context: Callable[[str], str],
    is_manual_queue_context: Callable[[str], bool],
    queue_filters_from_context: Callable[[str], tuple[str, str]],
    button_style_danger: str | None = None,
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    if status != "posted":
        rows.extend(
            two_column_rows(
                [
                    callback_button("⏱ +1ч", callback_data=f"pt:{post_id}:{status}:{offset}:h1"),
                    callback_button("🌙 19:00", callback_data=f"pt:{post_id}:{status}:{offset}:e19"),
                    callback_button("🌤 Завтра 10:00", callback_data=f"pt:{post_id}:{status}:{offset}:t10"),
                    callback_button("🚀 Опубликовать сейчас", callback_data=f"ppc:{post_id}:{status}:{offset}"),
                    callback_button("✍️ Редактировать вручную", callback_data=f"pm:{post_id}:{status}:{offset}"),
                    callback_button("🤖 Редактировать через LLM", callback_data=f"pa:{post_id}:{status}:{offset}"),
                    callback_button("🧩 Добавить футер", callback_data=f"pf:{post_id}:{status}:{offset}"),
                ]
            )
        )
        rows.append(
            [
                callback_button(
                    "🗑 Нерелевантно / удалить",
                    callback_data=f"pdd:{post_id}:{status}:{offset}",
                    style=button_style_danger,
                )
            ]
        )
    else:
        rows.append([callback_button("🔄 Обновить карточку", callback_data=f"pv:{post_id}:{status}:{offset}")])

    if status == "draft":
        rows.append([callback_button("🟡 На проверку", callback_data=f"rr:{post_id}:{status}:{offset}")])
    if status in ("review", "failed"):
        rows.append([callback_button("✅ В готовые", callback_data=f"pr:{post_id}:{status}:{offset}")])

    rows.append([callback_button(*_post_card_back_button(status=status, offset=offset, is_auto_queue_context=is_auto_queue_context, auto_queue_filters_from_context=auto_queue_filters_from_context, is_calendar_context=is_calendar_context, calendar_date_from_context=calendar_date_from_context, is_theme_context=is_theme_context, theme_from_context=theme_from_context, is_source_context=is_source_context, source_from_context=source_from_context, is_manual_queue_context=is_manual_queue_context, queue_filters_from_context=queue_filters_from_context))])
    rows.append([callback_button("🏠 Рабочий стол", callback_data="refresh")])
    return rows


def _post_card_back_button(
    *,
    status: str,
    offset: int,
    is_auto_queue_context: Callable[[str], bool],
    auto_queue_filters_from_context: Callable[[str], tuple[str, str]],
    is_calendar_context: Callable[[str], bool],
    calendar_date_from_context: Callable[[str], str],
    is_theme_context: Callable[[str], bool],
    theme_from_context: Callable[[str], str],
    is_source_context: Callable[[str], bool],
    source_from_context: Callable[[str], str],
    is_manual_queue_context: Callable[[str], bool],
    queue_filters_from_context: Callable[[str], tuple[str, str]],
) -> tuple[str, str]:
    if status == "review":
        return ("🔙 К проверке", f"rv:all:all:all:{offset}")
    if is_auto_queue_context(status):
        queue_filter, theme_filter = auto_queue_filters_from_context(status)
        return ("🔙 К автоочереди", f"aq:{queue_filter}:{theme_filter}:{offset}")
    if is_calendar_context(status):
        return ("🔙 К календарю", f"cal:day:{calendar_date_from_context(status)}")
    if is_theme_context(status):
        return ("🔙 К тематике", f"th:{theme_from_context(status)}:{offset}")
    if is_source_context(status):
        return ("🔙 К источнику", f"src:{source_from_context(status)}:{offset}")
    if is_manual_queue_context(status):
        queue_filter, theme_filter = queue_filters_from_context(status)
        return ("🔙 К очереди", f"mq:{queue_filter}:{theme_filter}:{offset}")
    return ("🔙 К списку", f"pl:{status}:{offset}")


def build_publish_confirm_keyboard_rows(
    *,
    post_id: str,
    status: str,
    offset: int,
    callback_button: InlineButtonFactory,
) -> list[list[Any]]:
    return [
        [callback_button("✅ Подтвердить публикацию", callback_data=f"ppy:{post_id}:{status}:{offset}")],
        _back_home_row(back_callback=f"ppn:{post_id}:{status}:{offset}", callback_button=callback_button),
    ]


def build_publish_reason_keyboard_rows(
    *,
    post_id: str,
    status: str,
    offset: int,
    callback_button: InlineButtonFactory,
) -> list[list[Any]]:
    return [_back_home_row(back_callback=f"ppn:{post_id}:{status}:{offset}", callback_button=callback_button)]


def build_delete_reason_keyboard_rows(
    *,
    post_id: str,
    status: str,
    offset: int,
    callback_button: InlineButtonFactory,
) -> list[list[Any]]:
    return [_back_home_row(back_callback=f"pdn:{post_id}:{status}:{offset}", callback_button=callback_button)]


def build_delete_confirm_keyboard_rows(
    *,
    post_id: str,
    status: str,
    offset: int,
    callback_button: InlineButtonFactory,
) -> list[list[Any]]:
    return [
        [callback_button("🗑 Удалить пост", callback_data=f"pdy:{post_id}:{status}:{offset}")],
        _back_home_row(back_callback=f"pdn:{post_id}:{status}:{offset}", callback_button=callback_button),
    ]


def build_batch_publish_reason_keyboard_rows(
    *,
    queue_filter: str,
    offset: int,
    mode: str,
    callback_button: InlineButtonFactory,
) -> list[list[Any]]:
    return [_back_home_row(back_callback=f"mbn:{queue_filter}:{offset}:{mode}", callback_button=callback_button)]


def build_batch_publish_confirm_keyboard_rows(
    *,
    queue_filter: str,
    offset: int,
    mode: str,
    callback_button: InlineButtonFactory,
) -> list[list[Any]]:
    return [
        [callback_button("✅ Подтвердить пакетную публикацию", callback_data=f"mbc:{queue_filter}:{offset}:{mode}")],
        _back_home_row(back_callback=f"mbn:{queue_filter}:{offset}:{mode}", callback_button=callback_button),
    ]


def _back_home_row(*, back_callback: str, callback_button: InlineButtonFactory) -> list[Any]:
    return [
        callback_button("🔙 Назад", callback_data=back_callback),
        callback_button("🏠 Рабочий стол", callback_data="refresh"),
    ]
