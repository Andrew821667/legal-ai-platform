from __future__ import annotations

from datetime import datetime, timezone

from news.pipeline import (
    ArticleCandidate,
    RAGExample,
    build_source_hash,
    canonicalize_url,
    choose_top_articles,
    normalize_rubric_to_pillar,
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
