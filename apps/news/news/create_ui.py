from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


def build_create_start_text(
    *,
    post_kind_order: Sequence[str],
    post_kind_label: Callable[[str], str],
    post_kind_structure: Callable[[str], str],
    post_kind_screen_template: Callable[[str], str],
) -> str:
    post_types = "\n".join(
        f"• {post_kind_label(kind)} — {post_kind_structure(kind)}"
        for kind in post_kind_order
    )
    return (
        "Создание нового поста\n\n"
        "Контур ручного редактора:\n"
        "1. Выбираете режим, тип поста и тематику\n"
        "2. Добавляете медиа и, если нужно, ссылку на источник\n"
        "3. Присылаете материал: текст, тезисы или Telegram-транскриб\n"
        "4. Получаете драфт, правите и отправляете в очередь\n\n"
        "Режимы:\n"
        "✍️ вручную — вы задаете основной текст сами\n"
        "🤖 через LLM — вы даете материал, бот собирает черновик\n\n"
        "🎙 из транскриба / voice — вы даете текстовую расшифровку голосового или устного материала, "
        "бот мягко очищает устную речь и собирает драфт\n\n"
        f"Доступные типы:\n{post_types}\n\n"
        "Сильные опорные типы:\n"
        f"{post_kind_label('promo_offer')}\n{post_kind_screen_template('promo_offer')}\n\n"
        f"{post_kind_label('opinion')}\n{post_kind_screen_template('opinion')}\n\n"
        f"{post_kind_label('case_story')}\n{post_kind_screen_template('case_story')}\n\n"
        "Далее сможете сохранить материал в черновики, на проверку или сразу в автоплан публикации."
    )


def build_create_preview_text(
    *,
    draft: dict[str, Any],
    compose_create_text: Callable[[dict[str, Any]], str],
    strip_html_markup: Callable[[str], str],
    post_kind_label: Callable[[str], str],
    theme_label: Callable[[str], str],
    post_kind_structure: Callable[[str], str],
    post_kind_screen_template: Callable[[str], str],
    theme_note: Callable[[str], str],
    footer_mode_label: Callable[[str], str],
    media_preview_label: Callable[[str, int], str],
) -> str:
    title = str(draft.get("title") or "Без заголовка")
    text = strip_html_markup(compose_create_text(draft))
    preview = text if len(text) <= 2500 else text[:2500] + "\n\n…"
    mode = str(draft.get("mode") or "manual")
    mode_label = "LLM" if mode == "ai" else "ручной"
    kind = str(draft.get("kind") or "")
    theme = str(draft.get("theme") or "")
    source_material = str(draft.get("source_material") or "").strip()
    source_url = str(draft.get("source_url") or "").strip()
    media_urls = draft.get("media_urls") or []
    footer = str(draft.get("footer_text") or "").strip()
    footer_reason = str(draft.get("footer_fit_reason") or "").strip()
    footer_state = "добавлен по смыслу" if footer else "не добавлен"
    media_block = (
        "Порядок медиа:\n"
        + "\n".join(media_preview_label(item, index) for index, item in enumerate(media_urls, start=1))
        + "\n"
        if media_urls
        else ""
    )
    return "".join(
        [
            "Черновик нового поста\n\n",
            f"Заголовок: {title}\n",
            f"Тип: {post_kind_label(kind)}\n",
            f"Тема: {theme_label(theme)}\n",
            f"Режим: {mode_label}\n",
            f"Шаблон: {post_kind_structure(kind)}\n",
            f"Опорный шаблон:\n{post_kind_screen_template(kind)}\n",
            f"Медиа: {'да' if media_urls else 'нет'}\n",
            media_block,
            f"Ссылка: {source_url[:180]}\n" if source_url else "Ссылка: нет\n",
            f"Длина итогового текста: {len(text)} символов\n",
            f"Материал: {source_material[:220]}\n" if source_material else "",
            f"Фокус темы: {theme_note(theme)}\n" if theme else "",
            f"Футер: {footer_mode_label(kind)}\n",
            f"Статус футера: {footer_state}\n",
            f"Причина: {footer_reason[:180]}\n" if footer_reason else "",
            f"Текст футера: {footer[:180]}\n" if footer else "",
            "\n",
            f"{preview}\n\n",
            "Можно доработать черновик или сразу сохранить:",
        ]
    )
