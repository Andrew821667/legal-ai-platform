from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any


ScreenGuide = Callable[[str, list[str]], str]


def build_themes_text(
    *,
    counts: Mapping[str, int],
    generation_counts: Mapping[str, int],
    enabled_generation_themes_count: int,
    active_longread_topics_count: int,
    longread_topics_total: int,
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    total_archive = sum(max(0, int(value)) for value in counts.values())
    return (
        "Тематики контента\n\n"
        "Раздел теперь разделен на 3 отдельных блока:\n"
        "1) 🗞 Ежедневные/регулярные посты (темы автогенерации)\n"
        "2) 📚 Воскресные лонгриды (отдельный пул тем)\n"
        "3) 🗂 Архивные корзины (уже созданные посты)\n\n"
        + guide(
            "Центр управления темами генерации и публикаций.",
            [
                "Откройте «Ежедневные», чтобы включить/выключить контент-темы автогенерации.",
                "Откройте «Лонгриды», чтобы настроить пул воскресных тем.",
                "Откройте «Архив», чтобы смотреть уже созданные посты по тематикам.",
            ],
        )
        + "\n\n"
        f"Активно ежедневных тем: {enabled_generation_themes_count}/{len(generation_counts)}\n"
        f"Активно тем лонгридов: {active_longread_topics_count}/{longread_topics_total}\n"
        f"Постов в архивных корзинах: {total_archive}\n\n"
        "Выберите нужный блок кнопками ниже."
    )


def build_themes_daily_text(
    *,
    generation_theme_keys: Sequence[str],
    generation_theme_counts: Mapping[str, int],
    enabled_generation_themes: set[str],
    generation_theme_label: Callable[[str], str],
    generation_theme_note: Callable[[str], str],
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    lines = [
        "Ежедневные/регулярные темы автогенерации",
        "",
        "Эти тумблеры влияют на генерацию ежедневных постов, обзоров недели и юмора.",
        "Воскресный лонгрид настраивается отдельно в разделе «Лонгриды».",
        "Быстрые действия: «Включить все» и «Профиль канала» (юридический фокус + ограниченный общий AI).",
        "",
        guide(
            "Матрица активных тем генерации.",
            [
                "Нажатие на тему переключает ее состояние (вкл/выкл).",
                "Кнопка «Профиль канала» быстро применяет рекомендуемый набор тем.",
            ],
        ),
        "",
    ]
    for theme_key in generation_theme_keys:
        mark = "✅" if theme_key in enabled_generation_themes else "☐"
        lines.append(f"• {mark} {generation_theme_label(theme_key)} — {generation_theme_counts.get(theme_key, 0)}")
        lines.append(f"  {generation_theme_note(theme_key)}")
    return "\n".join(lines)


def build_themes_archive_text(
    *,
    counts: Mapping[str, int],
    pillar_labels: Mapping[str, str],
    pillar_badge: Callable[[str], str],
    pillar_rubrics: Mapping[str, Sequence[str]],
    rubric_label: Callable[[str], str],
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    target_share = {
        "regulation": "30%",
        "case": "20%",
        "implementation": "30%",
        "tools": "15%",
        "market": "5%",
    }
    lines = [
        "Архивные корзины публикаций",
        "",
        "Здесь только уже созданные посты (на проверке / готовые / опубликованные / ошибки).",
        "Нажмите на корзину, чтобы открыть список постов по тематике.",
        "",
        guide(
            "Архив по тематическим корзинам.",
            [
                "Откройте корзину, чтобы посмотреть материалы этой тематики.",
                "Используйте статистику для балансировки контент-микса.",
            ],
        ),
        "",
    ]
    for pillar, label in pillar_labels.items():
        rubric_labels = ", ".join(rubric_label(item) for item in pillar_rubrics.get(pillar, ()))
        lines.append(
            f"• {pillar_badge(pillar)} {label}: {counts.get(pillar, 0)} пост(ов), целевая доля {target_share.get(pillar, 'n/a')}"
        )
        if rubric_labels:
            lines.append(f"  Рубрики: {rubric_labels}")
    return "\n".join(lines)


def build_theme_posts_text(
    *,
    pillar_label: str,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    page_size: int,
    rubric_label: Callable[[str], str],
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
            f"Тематика: {pillar_label}\n\n"
            + guide(
                "Список постов в выбранной тематической корзине.",
                [
                    "Откройте карточку поста для модерации.",
                    "Переходите по страницам кнопками «Назад/Далее».",
                ],
            )
            + f"\n\nСтраница: {current_page}/{total_pages}\n\nПостов пока нет."
        )

    lines = [
        f"Тематика: {pillar_label}",
        "",
        guide(
            "Список постов в выбранной тематической корзине.",
            [
                "Откройте карточку поста для модерации.",
                "Переходите по страницам кнопками «Назад/Далее».",
            ],
        ),
        "",
        f"Всего: {total}",
        f"Страница: {current_page}/{total_pages}",
        "",
    ]
    for idx, row in enumerate(rows, start=offset + 1):
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        rubric = rubric_label(str(row.get("rubric") or ""))
        status = str(row.get("status") or "")
        publication_kind = publication_kind_resolver(row)
        lines.append(f"{idx}. {status_badge(status)} {publication_kind_badge(publication_kind)} {title[:82]}")
        lines.append(f"   Рубрика: {rubric} | {publication_kind_label(publication_kind)}")
    return "\n".join(lines)
