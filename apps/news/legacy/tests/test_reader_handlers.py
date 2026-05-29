import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.bot import reader_handlers
from app.bot.reader_handlers import (
    _build_weekly_digest_text,
    _build_article_detail_text,
    _normalize_reader_text,
    get_article_keyboard,
)
from app.models.reader_publications import ReaderPublication


def _publication(**overrides) -> ReaderPublication:
    payload = {
        "id": uuid4(),
        "title": '«Тестовый» заголовок',
        "text": "Первый абзац — с цитатой…",
        "source_url": "https://example.com/article",
        "channel_username": "ai_verdict",
        "telegram_message_id": 321,
        "publish_at": datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc),
        "status": "posted",
    }
    payload.update(overrides)
    return ReaderPublication(**payload)


def test_normalize_reader_text_removes_special_symbols_and_markup() -> None:
    cleaned = _normalize_reader_text(
        '«Цитата» — это тест…<br><ul><li>Пункт</li></ul>\n> markdown quote',
        multiline=True,
    )

    assert cleaned == '"Цитата" - это тест...\n- Пункт\nmarkdown quote'


def test_get_article_keyboard_includes_source_links() -> None:
    keyboard = get_article_keyboard(
        "pub-1",
        source_url="https://example.com/original",
        channel_post_url="https://t.me/ai_verdict/42",
    )

    buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert any(button.text == "🌐 Статья" and button.callback_data == "web:article:pub-1" for button in buttons)
    assert any(button.text == "📣 Пост в канале" and button.url == "https://t.me/ai_verdict/42" for button in buttons)


def test_reader_onboarding_intro_explains_platform_context() -> None:
    intro = reader_handlers._PLATFORM_READER_INTRO
    assert "часть платформы AI Verdict" in intro
    assert "Contract AI" in intro
    assert "ассистент" in intro
    assert "Mini App" in intro


def test_build_article_detail_text_truncates_and_sanitizes() -> None:
    article = _publication(text=("«Очень длинный» текст… " * 400))

    detail_text = _build_article_detail_text(article)

    assert '«' not in detail_text
    assert '»' not in detail_text
    assert "..." in detail_text
    assert "Текст сокращен из-за лимита Telegram" in detail_text


def test_reader_publication_channel_post_url() -> None:
    article = _publication(channel_username="@ai_verdict", telegram_message_id=777)
    assert article.channel_post_url == "https://t.me/ai_verdict/777"


def test_build_weekly_digest_text_uses_llm_summary(monkeypatch) -> None:
    class _StubLLM:
        async def generate_completion(self, **kwargs):
            assert kwargs["max_tokens"] == 480
            return "Главный тренд недели: компании проверяют полезные AI-сценарии."

    monkeypatch.setattr(reader_handlers.settings, "reader_weekly_digest_timeout_seconds", 22, raising=False)
    monkeypatch.setattr(reader_handlers.settings, "reader_weekly_digest_source_limit", 5, raising=False)
    monkeypatch.setattr(reader_handlers.settings, "reader_weekly_digest_source_preview_chars", 180, raising=False)
    monkeypatch.setattr("app.modules.llm_provider.get_llm_provider", lambda provider: _StubLLM())

    text = asyncio.run(_build_weekly_digest_text([_publication()], db=None))

    assert "📆 <b>Недельный дайджест для вас</b>" in text
    assert "Главный тренд недели" in text
    assert "Ниже добавил карточки ключевых публикаций." in text
