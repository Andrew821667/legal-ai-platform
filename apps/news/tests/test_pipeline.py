from __future__ import annotations

from datetime import datetime, timezone

from news.pipeline import (
    ArticleCandidate,
    RAGExample,
    build_source_hash,
    canonicalize_source_url,
    canonicalize_url,
    choose_top_articles,
    is_specialized_candidate,
    normalize_rubric_to_pillar,
    normalize_post_text,
    parse_schedule_slots,
    select_rag_examples,
)


def test_parse_schedule_slots() -> None:
    slots = parse_schedule_slots("10:00, 13:15,17:45")
    assert slots == [(10, 0), (13, 15), (17, 45)]


def test_canonicalize_url_removes_tracking_and_www() -> None:
    assert canonicalize_url("https://www.example.com/a/b?utm=1#test") == "https://example.com/a/b"


def test_source_hash_uses_canonical_url() -> None:
    url = "https://www.example.com/a?utm=123"
    title = "Новая AI система в суде"
    hash1 = build_source_hash(url, title, datetime(2026, 2, 25, tzinfo=timezone.utc))
    hash2 = build_source_hash("https://example.com/a", title, datetime(2026, 2, 26, tzinfo=timezone.utc))
    assert hash1 == hash2


def test_choose_top_articles_filters_low_relevance() -> None:
    now = datetime(2026, 2, 25, tzinfo=timezone.utc)
    articles = [
        ArticleCandidate(
            source_url="https://src",
            article_url="https://src/1",
            title="AI и комплаенс в юридическом департаменте",
            summary="Практический кейс внедрения ИИ и LegalTech",
            published_at=now,
        ),
        ArticleCandidate(
            source_url="https://src",
            article_url="https://src/2",
            title="Погода на выходные",
            summary="Небольшой обзор погодных условий",
            published_at=now,
        ),
    ]

    selected = choose_top_articles(articles, limit=2, now_utc=now)
    assert len(selected) == 1
    assert selected[0].article_url == "https://src/1"


def test_specialized_filter_rejects_generic_ai_story() -> None:
    now = datetime(2026, 3, 3, tzinfo=timezone.utc)
    article = ArticleCandidate(
        source_url="https://habr.com/ru/rss/news/?fl=ru",
        article_url="https://habr.com/ru/news/roman-game",
        title="ИИ расшифровал правила древней римской игры",
        summary="Археологи использовали нейросеть для реконструкции правил настольной игры.",
        published_at=now,
    )
    assert not is_specialized_candidate(article)


def test_specialized_filter_rejects_ai_without_legal_context_from_tech_source() -> None:
    now = datetime(2026, 3, 3, tzinfo=timezone.utc)
    article = ArticleCandidate(
        source_url="https://habr.com/ru/rss/news/?fl=ru",
        article_url="https://habr.com/ru/news/store-bot",
        title="Разработчик создал Telegram-бота для заказа продуктов через LLM",
        summary="Сервис автоматизирует бытовой заказ продуктов и собирает корзину по команде пользователя.",
        published_at=now,
    )
    assert not is_specialized_candidate(article)


def test_choose_top_articles_limits_same_source() -> None:
    now = datetime(2026, 2, 25, tzinfo=timezone.utc)
    articles = [
        ArticleCandidate(
            source_url="https://source-a.com/rss",
            article_url=f"https://source-a.com/{i}",
            title="AI и комплаенс",
            summary="Практический кейс внедрения AI в юридической функции",
            published_at=now,
        )
        for i in range(3)
    ] + [
        ArticleCandidate(
            source_url="https://source-b.com/rss",
            article_url="https://source-b.com/1",
            title="AI в договорной работе",
            summary="Автоматизация redline и контроль рисков в контрактах",
            published_at=now,
        )
    ]

    selected = choose_top_articles(articles, limit=3, now_utc=now, max_per_source=1)
    assert len(selected) == 2
    domains = {canonicalize_url(item.article_url).split("/")[2] for item in selected}
    assert "source-a.com" in domains
    assert "source-b.com" in domains


def test_choose_top_articles_prefers_higher_priority_source() -> None:
    now = datetime(2026, 2, 25, tzinfo=timezone.utc)
    candidate_a = ArticleCandidate(
        source_url="https://source-a.com/rss",
        article_url="https://source-a.com/1",
        title="AI в договорной работе",
        summary="Автоматизация redline, юридические риски, workflow и legal ops.",
        published_at=now,
    )
    candidate_b = ArticleCandidate(
        source_url="https://source-b.com/rss",
        article_url="https://source-b.com/1",
        title="AI в договорной работе",
        summary="Автоматизация redline, юридические риски, workflow и legal ops.",
        published_at=now,
    )

    selected = choose_top_articles(
        [candidate_b, candidate_a],
        limit=1,
        now_utc=now,
        source_priority_weights={
            "https://source-a.com/rss": 1.8,
            "https://source-b.com/rss": 0.8,
        },
    )
    assert len(selected) == 1
    assert selected[0].article_url == "https://source-a.com/1"


def test_choose_top_articles_limits_broad_ai_bucket() -> None:
    now = datetime(2026, 2, 25, tzinfo=timezone.utc)
    articles = [
        ArticleCandidate(
            source_url="https://t.me/allthingslegal",
            article_url="https://t.me/allthingslegal/1",
            title="AI в договорной работе и legal ops",
            summary="Практический кейс для юротдела: AI помогает в договорном процессе и автоматизации юридической функции.",
            published_at=now,
        ),
        ArticleCandidate(
            source_url="https://news.google.com/rss/search?q=frontier",
            article_url="https://example.com/frontier-1",
            title="Frontier AI models reshape enterprise workflows for legal teams",
            summary="Enterprise AI tools create ideas for legal workflow automation, contract review and in-house legal transformation.",
            published_at=now,
        ),
        ArticleCandidate(
            source_url="https://news.google.com/rss/search?q=enterprise-ai",
            article_url="https://example.com/enterprise-2",
            title="Enterprise AI launches new copilots for corporate departments",
            summary="The launch suggests ideas for legal automation, intake triage and AI-assisted contract work inside corporate teams.",
            published_at=now,
        ),
    ]

    selected = choose_top_articles(
        articles,
        limit=3,
        now_utc=now,
        source_bucket_weights={
            canonicalize_source_url("https://t.me/allthingslegal"): "core",
            canonicalize_source_url("https://news.google.com/rss/search?q=frontier"): "broad_ai",
            canonicalize_source_url("https://news.google.com/rss/search?q=enterprise-ai"): "broad_ai",
        },
        max_bucket_counts={"broad_ai": 1},
    )

    assert len(selected) == 2
    selected_urls = {item.article_url for item in selected}
    assert "https://t.me/allthingslegal/1" in selected_urls
    assert len({"https://example.com/frontier-1", "https://example.com/enterprise-2"} & selected_urls) == 1


def test_select_rag_examples_returns_related_texts() -> None:
    examples = [
        RAGExample(title="AI комплаенс", text="Риски персональных данных и регуляторика", rubric="compliance"),
        RAGExample(title="Рынок такси", text="Новый тариф", rubric="other"),
    ]

    selected = select_rag_examples(
        query_text="ИИ и комплаенс для персональных данных",
        examples=examples,
        top_k=2,
    )
    assert len(selected) == 1
    assert selected[0].title == "AI комплаенс"


def test_normalize_rubric_to_pillar() -> None:
    assert normalize_rubric_to_pillar("compliance") == "regulation"
    assert normalize_rubric_to_pillar("unknown", "Рынок AI и инвестиции в LegalTech") == "market"


def test_normalize_post_text_trims_without_cutting_html_tag() -> None:
    text = "<b>Заголовок</b>\n\n" + ("Юридический AI-сигнал. " * 400) + '<a href="https://example.com">источник</a>'
    normalized = normalize_post_text(text)
    assert len(normalized) <= 4000
    assert normalized.count("<b>") == normalized.count("</b>")
    assert normalized.count("<a ") == normalized.count("</a>")
    assert not normalized.endswith("<")
