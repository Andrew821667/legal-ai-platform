from __future__ import annotations

from collections.abc import Callable
from typing import Any

from news.telegram_vpn_notice import EXTERNAL_LINK_VPN_NOTICE_TEXT, has_external_non_telegram_link


ScreenGuide = Callable[[str, list[str]], str]
FeedbackSnapshotFormatter = Callable[[dict[str, Any] | None], str]


def build_post_card_text(
    *,
    post: dict[str, Any],
    strip_html_markup: Callable[[str], str],
    post_format_label: Callable[[dict[str, Any]], str],
    row_publication_kind: Callable[[dict[str, Any]], str],
    publication_kind_badge: Callable[[str], str],
    publication_kind_label: Callable[[str], str],
    rubric_to_pillar: Callable[[str, str], str],
    pillar_display: Callable[[str], str],
    rubric_label: Callable[[str], str],
    status_badge: Callable[[str], str],
    status_label: Callable[[str], str],
    feedback_snapshot_formatter: FeedbackSnapshotFormatter,
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    title = str(post.get("title") or "Без заголовка")
    publish_at = str(post.get("publish_at") or "") or "—"
    status = str(post.get("status") or "")
    text = strip_html_markup(str(post.get("text") or ""))
    format_type = str(post.get("format_type") or "n/a")
    format_label = post_format_label(post)
    publication_kind = row_publication_kind(post)
    cta_type = str(post.get("cta_type") or "n/a")
    rubric = str(post.get("rubric") or "")
    pillar = rubric_to_pillar(rubric, f"{title}\n{text}")
    telegram_message_id = post.get("telegram_message_id")
    posted_at = str(post.get("posted_at") or "")
    preview = text if len(text) <= 1800 else text[:1800] + "\n\n…"
    source_url = str(post.get("source_url") or "")
    feedback_snapshot = post.get("feedback_snapshot") or {}
    badge = status_badge(status)
    label = status_label(status)

    parts = [
        "Карточка поста",
        "",
        guide(
            "Детальный экран одного поста.",
            [
                "Используйте кнопки публикации, редактирования и переноса статуса.",
                "Перед публикацией проверьте feedback, источник и фрагмент текста.",
            ],
        ),
        "",
        f"🆔 {post.get('id')} | {badge} {label}",
        f"📰 {title}",
        f"📌 {publication_kind_badge(publication_kind)} {publication_kind_label(publication_kind)}",
        f"🧭 {pillar_display(pillar)} | {rubric_label(rubric)}",
        f"🧩 {format_label} | CTA: {cta_type}",
        f"🗓 План публикации: {publish_at}",
        f"🔧 Технический формат: {format_type}",
    ]
    if telegram_message_id:
        parts.append(f"📨 Telegram message_id: {telegram_message_id}")
    if posted_at:
        parts.append(f"✅ Опубликован: {posted_at}")
    if source_url:
        parts.append(f"🔗 Источник: {source_url}")
        if has_external_non_telegram_link(source_url):
            parts.append(EXTERNAL_LINK_VPN_NOTICE_TEXT)
    parts.extend(
        [
            "",
            feedback_snapshot_formatter(feedback_snapshot),
            "",
            "Текст (фрагмент):",
            "",
            preview,
        ]
    )
    return "\n".join(parts)
