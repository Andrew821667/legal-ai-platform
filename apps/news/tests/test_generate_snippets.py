from __future__ import annotations

from news.generate import _normalize_snippet


def test_normalize_snippet_strips_markup_source_and_footer() -> None:
    raw = (
        "<b>Заголовок</b>\n\n"
        "Полезный абзац про внедрение AI в юрфункции.\n\n"
        "<b>Следующий шаг</b>\n"
        "Если хотите, напишите в @legal_ai_helper_new_bot.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#LegalAI #AI #LegalTech"
    )
    normalized = _normalize_snippet(raw, 260)
    assert "<b>" not in normalized
    assert "Источник" not in normalized
    assert "#LegalAI" not in normalized
    assert "@legal_ai_helper_new_bot" not in normalized
    assert "Полезный абзац" in normalized

