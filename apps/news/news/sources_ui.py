from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any


ScreenGuide = Callable[[str, list[str]], str]


def _spec_value(spec: Any, field: str, default: Any = None) -> Any:
    if spec is None:
        return default
    if isinstance(spec, dict):
        return spec.get(field, default)
    return getattr(spec, field, default)


def build_sources_text(
    *,
    specs: Sequence[Any],
    counts_by_key: Mapping[str, Mapping[str, int]],
    enabled_map: Mapping[str, bool],
    page: int = 0,
    page_size: int = 12,
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    total_pages = max(1, (len(specs) + page_size - 1) // page_size)
    safe_page = max(0, min(page, total_pages - 1))
    start = safe_page * page_size
    chunk = specs[start : start + page_size]

    active_count = sum(
        1
        for spec in specs
        if bool(_spec_value(spec, "integrated", True)) and enabled_map.get(str(_spec_value(spec, "key", "")), True)
    )
    rss_count = sum(1 for spec in specs if str(_spec_value(spec, "kind", "")) in {"rss", "search_rss", "search_api"})
    telegram_count = sum(1 for spec in specs if str(_spec_value(spec, "kind", "")) == "telegram")

    lines = [
        "Источники новостей",
        "",
        "Здесь показан каталог источников с постраничной навигацией.",
        "Нажмите на источник, чтобы открыть карточку с описанием, статусом, URL и связанными постами.",
        "",
        guide(
            "Реестр RSS/Search/Telegram-источников для генерации.",
            [
                "Открывайте карточку источника, чтобы включать/выключать его.",
                "Листайте страницы кнопками «Стр. назад/далее».",
                "Используйте «Telegram-каналы» для управления каналами по отдельности.",
            ],
        ),
        "",
        f"Активных интегрированных источников: {active_count}",
        f"Всего источников в каталоге: {len(specs)}",
        f"RSS/Search: {rss_count} | Telegram: {telegram_count}",
        f"Страница: {safe_page + 1}/{total_pages}",
        "",
    ]

    for index, spec in enumerate(chunk, start=start + 1):
        key = str(_spec_value(spec, "key", ""))
        name = str(_spec_value(spec, "name", key))
        kind = str(_spec_value(spec, "kind", "source"))
        integrated = bool(_spec_value(spec, "integrated", True))
        enabled = enabled_map.get(key, True)
        row = counts_by_key.get(key, {})

        if not integrated:
            badge = "🟡"
            status = "ожидает настройки"
        elif enabled:
            badge = "✅"
            status = "включен"
        else:
            badge = "☐"
            status = "выключен"

        total = sum(int(row.get(item, 0)) for item in ("review", "scheduled", "posted", "failed"))
        lines.append(f"{index}. {badge} {name} [{kind}]")
        lines.append(f"   {status}; постов в истории: {total}")

    return "\n".join(lines)


def build_source_detail_text(
    *,
    source_key: str,
    spec: Any | None,
    enabled_map: Mapping[str, bool],
    counts: Mapping[str, int],
    telegram_channels: Sequence[str] | None = None,
    telegram_channel_enabled_map: Mapping[str, bool] | None = None,
    telegram_channel_group: Callable[[str], str] | None = None,
    telegram_channel_group_label: Callable[[str], str] | None = None,
    telegram_channel_label: Callable[[str], str] | None = None,
    screen_guide: ScreenGuide | None = None,
) -> str:
    if spec is None:
        return "Источник не найден."

    guide = screen_guide or (lambda _what, _actions: "")
    key = str(_spec_value(spec, "key", source_key))
    name = str(_spec_value(spec, "name", key))
    kind = str(_spec_value(spec, "kind", "source"))
    note = str(_spec_value(spec, "note", ""))
    url = str(_spec_value(spec, "url", "") or "")
    domain = str(_spec_value(spec, "domain", "") or "")
    integrated = bool(_spec_value(spec, "integrated", True))
    enabled = enabled_map.get(key, True)

    if not integrated:
        status = "🟡 Требует настройки"
    elif enabled:
        status = "✅ Включен"
    else:
        status = "☐ Выключен"

    lines = [
        f"Источник: {name}",
        "",
        guide(
            "Карточка одного источника.",
            [
                "Кнопкой «Включить/Выключить» управляйте участием источника в генерации.",
                "Кнопка «Посты по источнику» открывает историю материалов от этого источника.",
            ],
        ),
        "",
        f"Тип: {kind}",
        f"Статус: {status}",
        "",
        f"Описание: {note}",
    ]

    if url:
        lines.extend(["", f"URL: {url}"])
    if domain:
        lines.append(f"Домен: {domain}")

    if source_key == "telegram_channels":
        channels = list(telegram_channels or [])
        channel_enabled = telegram_channel_enabled_map or {}
        lines.extend(["", f"Подключенные каналы: {len(channels)}"])
        for group in ("legal", "ai"):
            group_fn = telegram_channel_group or (lambda _value: "legal")
            group_label_fn = telegram_channel_group_label or (lambda value: value)
            label_fn = telegram_channel_label or (lambda value: value)
            group_channels = [channel for channel in channels if group_fn(channel) == group]
            if not group_channels:
                continue
            lines.append(f"• {group_label_fn(group)}:")
            for channel in group_channels:
                slug = str(channel).strip().lower().removeprefix("@")
                badge = "✅" if channel_enabled.get(slug, True) else "☐"
                lines.append(f"  {badge} {label_fn(channel)}")

    lines.extend(
        [
            "",
            "Посты в истории:",
            f"• На проверке: {counts.get('review', 0)}",
            f"• Готовые: {counts.get('scheduled', 0)}",
            f"• Опубликованные: {counts.get('posted', 0)}",
            f"• Ошибки: {counts.get('failed', 0)}",
        ]
    )

    return "\n".join(lines)


def build_telegram_channel_detail_text(
    *,
    slug: str,
    enabled: bool,
    counts: Mapping[str, int],
    group_label: str,
    note: str,
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    normalized = str(slug).strip().lower().removeprefix("@")
    label = f"@{normalized}"

    lines = [
        f"Telegram-канал: {label}",
        "",
        guide(
            "Карточка Telegram-канала как отдельного источника.",
            [
                "Включайте/выключайте канал независимо от остальных.",
                "Используйте ссылку на канал для ручной проверки релевантности потока.",
            ],
        ),
        "",
        f"Группа: {group_label}",
        "",
        f"Статус: {'✅ Включен' if enabled else '☐ Выключен'}",
        "",
        f"Описание: {note}",
        "",
        "Роль в контуре:",
        "• используется как дополнительный специализированный источник идей и сигналов",
        "• проходит через topical filter и relevance gate",
        "• не должен тянуть в канал общий AI-шум без связи с правом и юрфункцией",
        "",
        "Посты в истории:",
        f"• На проверке: {counts.get('review', 0)}",
        f"• Готовые: {counts.get('scheduled', 0)}",
        f"• Опубликованные: {counts.get('posted', 0)}",
        f"• Ошибки: {counts.get('failed', 0)}",
        "",
        f"Ссылка: https://t.me/{normalized}",
    ]
    return "\n".join(lines)


def build_source_posts_text(
    *,
    source_label: str,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    page_size: int,
    status_badge: Callable[[str], str],
    publication_kind_badge: Callable[[str], str],
    publication_kind_label: Callable[[str], str],
    publication_kind_resolver: Callable[[dict[str, Any]], str],
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(total_pages, (offset // page_size) + 1)

    if not rows:
        return (
            f"Источник: {source_label}\n\n"
            + guide(
                "История постов, собранных из выбранного источника.",
                [
                    "Открывайте карточку поста для модерации или публикации.",
                    "Используйте пагинацию внизу для перехода по списку.",
                ],
            )
            + f"\n\nСтраница: {current_page}/{total_pages}\n\nПостов по этому источнику пока нет."
        )

    lines = [
        f"Источник: {source_label}",
        "",
        guide(
            "История постов, собранных из выбранного источника.",
            [
                "Открывайте карточку поста для модерации или публикации.",
                "Используйте пагинацию внизу для перехода по списку.",
            ],
        ),
        "",
        f"Всего постов: {total}",
        f"Страница: {current_page}/{total_pages}",
        "",
    ]

    for idx, row in enumerate(rows, start=offset + 1):
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        status = str(row.get("status") or "")
        publish_at = str(row.get("publish_at") or "")
        publication_kind = publication_kind_resolver(row)
        lines.append(f"{idx}. {status_badge(status)} {publication_kind_badge(publication_kind)} {title[:80]}")
        lines.append(f"   ⏰ {publish_at} | {publication_kind_label(publication_kind)}")

    return "\n".join(lines)
