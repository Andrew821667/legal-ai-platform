from __future__ import annotations

from news.create_ui import build_create_preview_text, build_create_start_text


def test_build_create_start_text_contains_core_sections() -> None:
    text = build_create_start_text(
        post_kind_order=["promo_offer", "opinion"],
        post_kind_label=lambda kind: {"promo_offer": "Промо", "opinion": "Мнение", "case_story": "Кейс"}[kind],
        post_kind_structure=lambda kind: {"promo_offer": "Боль -> решение", "opinion": "Тезис -> аргументы"}[kind],
        post_kind_screen_template=lambda kind: {
            "promo_offer": "Шаблон промо",
            "opinion": "Шаблон мнения",
            "case_story": "Шаблон кейса",
        }[kind],
    )
    assert "Создание нового поста" in text
    assert "Контур ручного редактора" in text
    assert "Доступные типы" in text
    assert "• Промо — Боль -> решение" in text
    assert "• Мнение — Тезис -> аргументы" in text
    assert "Сильные опорные типы" in text
    assert "Промо\nШаблон промо" in text
    assert "Мнение\nШаблон мнения" in text
    assert "Кейс\nШаблон кейса" in text


def test_build_create_preview_text_renders_full_snapshot() -> None:
    text = build_create_preview_text(
        draft={
            "title": "Новый материал",
            "mode": "ai",
            "kind": "opinion",
            "theme": "regulation",
            "source_material": "Входящий материал",
            "source_url": "https://example.com/source",
            "media_urls": ["tgphoto://1", "tgvideo://2"],
            "footer_text": "Релевантный футер",
            "footer_fit_reason": "Есть следующий шаг",
        },
        compose_create_text=lambda _draft: "<b>Тело</b> поста",
        strip_html_markup=lambda value: value.replace("<b>", "").replace("</b>", ""),
        post_kind_label=lambda kind: {"opinion": "Мнение"}[kind],
        theme_label=lambda theme: {"regulation": "Регулирование"}[theme],
        post_kind_structure=lambda kind: {"opinion": "Тезис -> аргументы"}[kind],
        post_kind_screen_template=lambda kind: {"opinion": "Опорный шаблон"}[kind],
        theme_note=lambda theme: {"regulation": "Фокус на нормах"}[theme],
        footer_mode_label=lambda _kind: "семантический через LLM",
        media_preview_label=lambda media_url, index: f"{index}. {media_url}",
    )
    assert "Черновик нового поста" in text
    assert "Заголовок: Новый материал" in text
    assert "Режим: LLM" in text
    assert "Тема: Регулирование" in text
    assert "Медиа: да" in text
    assert "Порядок медиа:\n1. tgphoto://1\n2. tgvideo://2\n" in text
    assert "Ссылка: https://example.com/source" in text
    assert "Материал: Входящий материал" in text
    assert "Футер: семантический через LLM" in text
    assert "Статус футера: добавлен по смыслу" in text
    assert "Причина: Есть следующий шаг" in text
    assert "Текст футера: Релевантный футер" in text
    assert "Тело поста" in text


def test_build_create_preview_text_truncates_and_uses_defaults() -> None:
    long_text = "x" * 2600
    text = build_create_preview_text(
        draft={"kind": "opinion", "media_urls": []},
        compose_create_text=lambda _draft: long_text,
        strip_html_markup=lambda value: value,
        post_kind_label=lambda kind: {"opinion": "Мнение"}[kind],
        theme_label=lambda theme: theme,
        post_kind_structure=lambda kind: {"opinion": "Структура"}[kind],
        post_kind_screen_template=lambda kind: {"opinion": "Шаблон"}[kind],
        theme_note=lambda theme: theme,
        footer_mode_label=lambda _kind: "mode",
        media_preview_label=lambda media_url, index: f"{index}. {media_url}",
    )
    assert "Заголовок: Без заголовка" in text
    assert "Режим: ручной" in text
    assert "Медиа: нет" in text
    assert "Ссылка: нет" in text
    assert "Статус футера: не добавлен" in text
    assert long_text[:2500] in text
    assert "\n\n…" in text
