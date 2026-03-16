from __future__ import annotations

from collections.abc import Callable
from typing import Any


ScreenGuide = Callable[[str, list[str]], str]


def build_posts_text(
    *,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    status: str,
    page_size: int,
    status_label: Callable[[str], str],
    status_badge: Callable[[str], str],
    publication_kind_badge: Callable[[str], str],
    publication_kind_label: Callable[[str], str],
    row_publication_kind: Callable[[dict[str, Any]], str],
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    label = status_label(status)
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(total_pages, (offset // page_size) + 1)

    if not rows:
        return (
            f"{label} (status={status})\n\n"
            + guide(
                "Список постов выбранного статуса.",
                [
                    "Откройте карточку поста для детального управления.",
                    "Используйте пагинацию и массовые кнопки внизу списка.",
                ],
            )
            + f"\n\nСтраница: {current_page}/{total_pages}\n\nСейчас записей нет."
        )

    lines = [
        f"{label}: {total}",
        "",
        guide(
            "Список постов выбранного статуса.",
            [
                "Откройте карточку поста для детального управления.",
                "Используйте пагинацию и массовые кнопки внизу списка.",
            ],
        ),
        "",
        f"Страница: {current_page}/{total_pages}",
        "",
    ]
    for idx, row in enumerate(rows, start=offset + 1):
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        publish_at = str(row.get("publish_at") or "")
        row_status = str(row.get("status") or status)
        publication_kind = row_publication_kind(row)
        lines.append(f"{idx}. {status_badge(row_status)} {publication_kind_badge(publication_kind)} {title[:86]}")
        lines.append(f"   ⏰ {publish_at} | {publication_kind_label(publication_kind)}")
    return "\n".join(lines)


def build_review_posts_text(
    *,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    review_filter: str,
    kind_filter: str,
    theme_filter: str,
    page_size: int,
    review_origin_label: Callable[[str], str],
    review_origin_badge: Callable[[str], str],
    publication_kind_label: Callable[[str], str],
    publication_kind_badge: Callable[[str], str],
    pillar_display: Callable[[str], str],
    pillar_label: Callable[[str], str],
    post_format_label: Callable[[dict[str, Any]], str],
    row_publication_kind: Callable[[dict[str, Any]], str],
    row_pillar: Callable[[dict[str, Any]], str],
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    filter_label = review_origin_label(review_filter)
    kind_label = "Все виды" if kind_filter == "all" else publication_kind_label(kind_filter)
    theme_label = "Все темы" if theme_filter == "all" else pillar_display(theme_filter)
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(total_pages, (offset // page_size) + 1)

    if not rows:
        return (
            "🟡 На проверке\n\n"
            + guide(
                "Ключевой список модерации перед публикацией.",
                [
                    "Фильтруйте материалы по источнику (AI/ручные), виду публикации и теме.",
                    "После проверки переводите выбранные посты в «Готовые».",
                ],
            )
            + "\n\n"
            f"Фильтр: {filter_label}\n"
            f"Вид: {kind_label}\n"
            f"Тема: {theme_label}\n\n"
            f"Страница: {current_page}/{total_pages}\n\n"
            "Сейчас записей нет."
        )

    lines = [
        "🟡 На проверке",
        "",
        guide(
            "Ключевой список модерации перед публикацией.",
            [
                "Фильтруйте материалы по источнику (AI/ручные), виду публикации и теме.",
                "После проверки переводите выбранные посты в «Готовые».",
            ],
        ),
        "",
        f"Фильтр: {filter_label}",
        f"Вид: {kind_label}",
        f"Тема: {theme_label}",
        f"Всего: {total}",
        f"Страница: {current_page}/{total_pages}",
        "",
    ]
    for idx, row in enumerate(rows, start=offset + 1):
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        publish_at = str(row.get("publish_at") or "")
        format_type = str(row.get("format_type") or "")
        publication_kind = row_publication_kind(row)
        pillar = row_pillar(row)
        lines.append(f"{idx}. {review_origin_badge(format_type)} {publication_kind_badge(publication_kind)} {title[:80]}")
        lines.append(f"   ⏰ {publish_at} | 🧭 {pillar_label(pillar)} | {post_format_label(row)}")
    return "\n".join(lines)
