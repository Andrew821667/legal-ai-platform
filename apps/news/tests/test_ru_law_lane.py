"""Право РФ — самостоятельная тема канала: коридор мимо ИИ-фильтров."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from news.pipeline import (
    ArticleCandidate,
    _SPECIALIZED_CANDIDATE_THRESHOLD,
    article_matches_enabled_generation_themes,
    interleave_ru_law,
    is_ru_law_candidate,
    passes_generation_scope,
    specialized_relevance_score,
)
from news.source_catalog import parse_active_source_keys, source_catalog

_CONSULTANT_FEED = "https://www.consultant.ru/rss/fd.xml"


def _article(title: str, summary: str = "", *, url: str = "https://example.com/a", source: str = "https://example.com/rss") -> ArticleCandidate:
    return ArticleCandidate(source_url=source, article_url=url, title=title, summary=summary, published_at=datetime.now(UTC))


def _consultant(summary: str) -> ArticleCandidate:
    return _article(
        "Письмо Минстроя России от 22.09.2026 N 59008-ДН/04",
        summary,
        url="https://www.consultant.ru/law/review/1.html",
        source=_CONSULTANT_FEED,
    )


def test_russian_law_change_for_people_is_the_ru_law_lane() -> None:
    housing = _consultant("Даны разъяснения по вопросу уменьшения размера платы за коммунальную услугу горячего водоснабжения")
    labour = _article(
        "КС РФ: работа в региональные нерабочие праздники оплачивается",
        "Конституционный суд указал, что работодатель обязан оплатить работнику такие дни",
    )
    assert is_ru_law_candidate(housing)
    assert is_ru_law_candidate(labour)
    # Без ИИ-маркеров, но проходит фильтры охвата и порог отбора.
    assert passes_generation_scope(housing)
    assert specialized_relevance_score(housing) >= _SPECIALIZED_CANDIDATE_THRESHOLD


def test_not_every_article_is_russian_law() -> None:
    assert not is_ru_law_candidate(_article("OpenAI выпустила новую модель", "Модель рассуждения для корпоративных клиентов"))
    assert not is_ru_law_candidate(_article("EU court rules on employer data retention", "The court said the employer must"))
    # Правовой акт без адресата-бизнеса или граждан (экспортные квоты) — мимо.
    assert not is_ru_law_candidate(_consultant("По 31 декабря 2026 г. устанавливаются тарифные квоты на экспорт семян рапса"))


def test_ru_law_is_every_third_in_the_queue() -> None:
    others = [_article(f"AI news {n}", "legal AI contract review") for n in range(4)]
    laws = [_consultant(f"Даны разъяснения собственникам жилья, вопрос {n}") for n in range(2)]
    queue = interleave_ru_law([*others, *laws], every=3)
    assert [is_ru_law_candidate(article) for article in queue] == [False, False, True, False, False, True]
    # Без чередования порядок не меняется; одни статьи права РФ — все подряд.
    assert interleave_ru_law([*others, *laws], every=0) == [*others, *laws]
    assert interleave_ru_law(laws, every=3) == laws


def test_ru_law_source_is_added_to_explicit_source_list() -> None:
    explicit = SimpleNamespace(news_source_keys="google_news_ru,artificial_lawyer", news_ru_law_source_keys="consultant_ru_law")
    assert parse_active_source_keys(explicit) == ["google_news_ru", "artificial_lawyer", "consultant_ru_law"]
    # Уже в списке — не дублируется; пустая настройка — ничего не добавляется.
    already = SimpleNamespace(news_source_keys="consultant_ru_law", news_ru_law_source_keys="consultant_ru_law")
    assert parse_active_source_keys(already) == ["consultant_ru_law"]
    off = SimpleNamespace(news_source_keys="google_news_ru", news_ru_law_source_keys="")
    assert parse_active_source_keys(off) == ["google_news_ru"]
    spec = source_catalog(explicit)["consultant_ru_law"]
    assert spec.url == _CONSULTANT_FEED and spec.integrated


def test_ai_themes_do_not_filter_out_ru_law() -> None:
    housing = _consultant("Даны разъяснения собственникам машино-мест в многоквартирном доме")
    assert article_matches_enabled_generation_themes(housing, {"contracts_ai"})


def test_russian_legal_feeds_bypass_the_vpn_proxy(monkeypatch) -> None:
    # Исходящий прокси пропускает только свой список адресов: consultant.ru
    # через него получал 403, напрямую — читается.
    from news import rss_fetcher

    monkeypatch.setattr(rss_fetcher.settings, "news_rss_proxy_url", "http://proxy:18081")
    monkeypatch.setattr(rss_fetcher.settings, "news_rss_direct_domains", "consultant.ru,pravo.ru")
    assert rss_fetcher.proxies_for(_CONSULTANT_FEED) == {"http": None, "https": None}
    assert rss_fetcher.proxies_for("https://news.google.com/rss/search?q=x") == {
        "http": "http://proxy:18081",
        "https": "http://proxy:18081",
    }
    monkeypatch.setattr(rss_fetcher.settings, "news_rss_proxy_url", "")
    assert rss_fetcher.proxies_for("https://news.google.com/rss") is None
