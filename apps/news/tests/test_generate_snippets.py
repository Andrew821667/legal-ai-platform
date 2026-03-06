from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import news.generate as generate_module
from news.generate import _normalize_snippet
from news.pipeline import ArticleCandidate


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


def test_collect_generation_previews_uses_fallback_for_synthetic_slot_rejection(monkeypatch) -> None:
    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self._payload

    class _FakeCoreClient:
        def __init__(self, *_: object, **__: object) -> None:
            return None

        def list_automation_controls(self, scope: str = "news") -> _FakeResponse:
            return _FakeResponse([])

    class _FakeRAG:
        def __init__(self, *_: object, **__: object) -> None:
            return None

        def find_context(self, *_: object, **__: object) -> list[object]:
            return []

    class _FakeWriter:
        generate_calls = 0
        fallback_calls = 0

        def generate_post(self, *_: object, **__: object):
            _FakeWriter.generate_calls += 1
            return None

        def fallback_post(self, *_: object, **__: object):
            _FakeWriter.fallback_calls += 1
            return {
                "title": "Субботний пост",
                "text": "<b>Субботний пост</b>\n\n<b>Ситуация недели</b>\nТест.\n\n<b>Почему это смешно</b>\nТест.\n\n<b>Где здесь практический смысл</b>\nТест.\n\n<b>Источник</b>: ссылка\n#LegalAI",
                "rubric": "legal_ops",
            }

    article = ArticleCandidate(
        source_url="https://example.com/rss",
        article_url="https://example.com/legal-ai",
        title="Legal AI сигнал",
        summary="Короткий сигнал про AI и юридическую автоматизацию.",
        published_at=datetime.now(timezone.utc),
    )

    monkeypatch.setattr(generate_module.settings, "api_key_news", "test-key", raising=False)
    monkeypatch.setattr(generate_module.settings, "openai_api_key", "test-key", raising=False)
    monkeypatch.setattr(generate_module.settings, "core_api_url", "http://core-api:8000", raising=False)
    monkeypatch.setattr(generate_module.settings, "tz_name", "UTC", raising=False)
    monkeypatch.setattr(generate_module.settings, "news_priority_domains", "", raising=False)
    monkeypatch.setattr(generate_module.settings, "news_max_per_source", 3, raising=False)
    monkeypatch.setattr(generate_module.settings, "news_similarity_threshold", 0.95, raising=False)
    monkeypatch.setattr(generate_module.settings, "news_telegram_cache_max_age_minutes", 60, raising=False)
    monkeypatch.setattr(generate_module.settings, "news_telegram_inline_fallback", False, raising=False)
    monkeypatch.setattr(generate_module, "CoreClient", _FakeCoreClient)
    monkeypatch.setattr(generate_module, "_load_controls", lambda client: [])
    monkeypatch.setattr(generate_module, "_collect_history", lambda client, tz: ([], set(), {}, [], [], set()))
    monkeypatch.setattr(generate_module, "resolve_source_urls", lambda *_args, **_kwargs: ["https://example.com/rss"])
    monkeypatch.setattr(generate_module, "source_priority_map", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(generate_module, "source_bucket_map", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(generate_module, "fetch_rss_articles", lambda *_args, **_kwargs: [article])
    monkeypatch.setattr(generate_module, "enabled_telegram_channels", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(generate_module, "article_matches_enabled_generation_themes", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(generate_module, "choose_top_articles", lambda *_args, **_kwargs: [article])
    monkeypatch.setattr(
        generate_module,
        "build_publish_plan",
        lambda *_args, **_kwargs: [
            SimpleNamespace(
                publish_at_local=datetime.now(timezone.utc),
                publication_kind="humor",
                format_type="humor",
                cta_type="soft",
                longread_topic=None,
            )
        ],
    )
    monkeypatch.setattr(generate_module, "PostedContentRAG", _FakeRAG)
    monkeypatch.setattr(generate_module, "LLMNewsWriter", _FakeWriter)

    result = generate_module.collect_generation_previews(1)

    assert len(result.previews) == 1
    assert result.previews[0]["publication_kind"] == "humor"
    assert _FakeWriter.generate_calls == 1
    assert _FakeWriter.fallback_calls == 1
