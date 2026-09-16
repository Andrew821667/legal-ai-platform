"""company_knowledge.py: RAG по знаниям компании (услуги/FAQ/сценарии/методология
с сайта) — вторая половина пункта 3 плана «умный ассистент». Снимок и эмбеддинги
кешируются с TTL, любой сбой (сеть, эмбеддинги) съедается — ответ клиенту важнее."""
import pytest

import company_knowledge


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    """Модульный кеш — глобальное состояние; каждый тест начинает с чистого листа."""
    monkeypatch.setattr(company_knowledge, "_cache_items", [])
    monkeypatch.setattr(company_knowledge, "_cache_embeddings", [])
    monkeypatch.setattr(company_knowledge, "_cache_loaded_at", 0.0)


def _item(title, text, href="/services/contracts-ai"):
    return {"id": title, "type": "service", "title": title, "text": text, "href": href}


# ── _refresh_cache_if_stale / _fetch_snapshot ───────────────────────────────

def test_refresh_fetches_and_embeds_once_per_item(monkeypatch):
    items = [_item("Проверка договоров", "AI-проверка договоров и рисков"), _item("Due diligence", "Обзор массива документов")]
    monkeypatch.setattr(company_knowledge, "_fetch_snapshot", lambda: items)
    embed_calls = []
    monkeypatch.setattr(
        company_knowledge.knowledge_engine.knowledge_engine,
        "get_embedding",
        lambda text: embed_calls.append(text) or [0.1, 0.2],
    )

    company_knowledge._refresh_cache_if_stale()

    assert company_knowledge._cache_items == items
    assert len(company_knowledge._cache_embeddings) == 2
    assert len(embed_calls) == 2  # по одному эмбеддингу на элемент, не на сообщение


def test_refresh_skips_when_cache_fresh(monkeypatch):
    monkeypatch.setattr(company_knowledge, "_cache_items", [_item("X", "Y")])
    monkeypatch.setattr(company_knowledge, "_cache_embeddings", [[0.1]])
    monkeypatch.setattr(company_knowledge, "_cache_loaded_at", company_knowledge.time.monotonic())

    def _fail():
        raise AssertionError("не должен обновлять свежий кеш")

    monkeypatch.setattr(company_knowledge, "_fetch_snapshot", _fail)

    company_knowledge._refresh_cache_if_stale()  # не должно упасть


def test_refresh_refetches_when_ttl_expired(monkeypatch):
    monkeypatch.setattr(company_knowledge.config, "WEB_KNOWLEDGE_CACHE_TTL_SECONDS", 100.0)
    monkeypatch.setattr(company_knowledge, "_cache_items", [_item("Старое", "старый текст")])
    monkeypatch.setattr(company_knowledge, "_cache_embeddings", [[0.1]])
    monkeypatch.setattr(company_knowledge, "_cache_loaded_at", company_knowledge.time.monotonic() - 200)

    new_items = [_item("Новое", "новый текст")]
    monkeypatch.setattr(company_knowledge, "_fetch_snapshot", lambda: new_items)
    monkeypatch.setattr(company_knowledge.knowledge_engine.knowledge_engine, "get_embedding", lambda text: [0.5])

    company_knowledge._refresh_cache_if_stale()

    assert company_knowledge._cache_items == new_items


def test_refresh_falls_back_to_stale_cache_on_network_error(monkeypatch):
    stale_items = [_item("Старое", "текст")]
    monkeypatch.setattr(company_knowledge, "_cache_items", stale_items)
    monkeypatch.setattr(company_knowledge, "_cache_embeddings", [[0.1]])
    monkeypatch.setattr(company_knowledge, "_cache_loaded_at", 0.0)  # протух

    def _boom():
        raise company_knowledge.urllib.error.URLError("сайт недоступен")

    monkeypatch.setattr(company_knowledge, "_fetch_snapshot", _boom)

    company_knowledge._refresh_cache_if_stale()  # не должно упасть

    assert company_knowledge._cache_items == stale_items  # старые данные остались
    assert company_knowledge._cache_loaded_at > 0  # не будет долбить эндпоинт каждое сообщение


def test_refresh_with_no_prior_cache_and_network_error_stays_empty(monkeypatch):
    def _boom():
        raise OSError("no route to host")

    monkeypatch.setattr(company_knowledge, "_fetch_snapshot", _boom)

    company_knowledge._refresh_cache_if_stale()

    assert company_knowledge._cache_items == []


def test_refresh_empty_snapshot_does_not_clear_existing_cache(monkeypatch):
    """Пустой ответ (сайт временно ничего не отдал) — не повод стирать то, что уже было."""
    stale_items = [_item("Было", "текст")]
    monkeypatch.setattr(company_knowledge, "_cache_items", stale_items)
    monkeypatch.setattr(company_knowledge, "_cache_embeddings", [[0.1]])
    monkeypatch.setattr(company_knowledge, "_cache_loaded_at", 0.0)
    monkeypatch.setattr(company_knowledge, "_fetch_snapshot", lambda: [])

    company_knowledge._refresh_cache_if_stale()

    assert company_knowledge._cache_items == stale_items


# ── find_relevant ────────────────────────────────────────────────────────

def test_find_relevant_filters_by_similarity_and_sorts(monkeypatch):
    items = [_item("Слабое совпадение", "почти не по теме"), _item("Сильное совпадение", "проверка договоров ИИ")]
    monkeypatch.setattr(company_knowledge, "_cache_items", items)
    monkeypatch.setattr(company_knowledge, "_cache_embeddings", [[1.0, 0.0], [0.0, 1.0]])
    monkeypatch.setattr(company_knowledge, "_cache_loaded_at", company_knowledge.time.monotonic())

    monkeypatch.setattr(company_knowledge.knowledge_engine.knowledge_engine, "get_embedding", lambda text: [0.0, 1.0])

    def _cos(a, b):
        return 1.0 if a == b else 0.2

    monkeypatch.setattr(company_knowledge.knowledge_engine.knowledge_engine, "cosine_similarity", _cos)

    results = company_knowledge.find_relevant("проверка договоров", min_similarity=0.6)

    assert len(results) == 1
    assert results[0][0]["title"] == "Сильное совпадение"


def test_find_relevant_empty_when_cache_empty(monkeypatch):
    monkeypatch.setattr(company_knowledge, "_fetch_snapshot", lambda: [])  # без сети: кеш пуст и остаётся пуст
    assert company_knowledge.find_relevant("что угодно") == []


def test_find_relevant_empty_when_query_embedding_fails(monkeypatch):
    monkeypatch.setattr(company_knowledge, "_cache_items", [_item("X", "Y")])
    monkeypatch.setattr(company_knowledge, "_cache_embeddings", [[0.1]])
    monkeypatch.setattr(company_knowledge, "_cache_loaded_at", company_knowledge.time.monotonic())
    monkeypatch.setattr(company_knowledge.knowledge_engine.knowledge_engine, "get_embedding", lambda text: [])

    assert company_knowledge.find_relevant("вопрос") == []


def test_find_relevant_respects_top_k(monkeypatch):
    items = [_item(f"Материал {i}", "текст про договоры") for i in range(5)]
    monkeypatch.setattr(company_knowledge, "_cache_items", items)
    monkeypatch.setattr(company_knowledge, "_cache_embeddings", [[1.0] for _ in items])
    monkeypatch.setattr(company_knowledge, "_cache_loaded_at", company_knowledge.time.monotonic())
    monkeypatch.setattr(company_knowledge.knowledge_engine.knowledge_engine, "get_embedding", lambda text: [1.0])
    monkeypatch.setattr(company_knowledge.knowledge_engine.knowledge_engine, "cosine_similarity", lambda a, b: 0.9)

    results = company_knowledge.find_relevant("договоры", top_k=2)

    assert len(results) == 2


# ── format_for_prompt / build_context ───────────────────────────────────

def test_format_for_prompt_empty_matches():
    assert company_knowledge.format_for_prompt([]) == ""


def test_format_for_prompt_includes_title_text_and_link():
    matches = [(_item("Проверка договоров", "Матрица рисков и первый проход по документу", "/services/contracts-ai"), 0.82)]
    block = company_knowledge.format_for_prompt(matches)

    assert "# База знаний компании" in block
    assert "Проверка договоров" in block
    assert "Матрица рисков" in block
    assert "/services/contracts-ai" in block


def test_build_context_short_query_returns_empty(monkeypatch):
    assert company_knowledge.build_context("ок") == ""
    assert company_knowledge.build_context(None) == ""


def test_build_context_end_to_end(monkeypatch):
    monkeypatch.setattr(company_knowledge, "_cache_items", [_item("Проверка договоров", "AI-проверка договоров")])
    monkeypatch.setattr(company_knowledge, "_cache_embeddings", [[1.0]])
    monkeypatch.setattr(company_knowledge, "_cache_loaded_at", company_knowledge.time.monotonic())
    monkeypatch.setattr(company_knowledge.knowledge_engine.knowledge_engine, "get_embedding", lambda text: [1.0])
    monkeypatch.setattr(company_knowledge.knowledge_engine.knowledge_engine, "cosine_similarity", lambda a, b: 0.9)

    result = company_knowledge.build_context("Как устроена проверка договоров нейросетью?")

    assert "Проверка договоров" in result


def test_build_context_swallows_exceptions(monkeypatch):
    def _boom():
        raise RuntimeError("cache corrupted")

    monkeypatch.setattr(company_knowledge, "find_relevant", lambda query, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    assert company_knowledge.build_context("Достаточно длинный вопрос про сервис") == ""


# ── _fetch_snapshot shape validation ────────────────────────────────────

def test_fetch_snapshot_parses_items_from_json(monkeypatch):
    import io

    body = b'{"items": [{"id": "faq-0", "type": "faq", "title": "Q", "text": "A", "href": "/#faq"}]}'

    class _FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(request, timeout=0):
        return _FakeResponse(body)

    monkeypatch.setattr(company_knowledge.urllib.request, "urlopen", _fake_urlopen)

    items = company_knowledge._fetch_snapshot()

    assert items == [{"id": "faq-0", "type": "faq", "title": "Q", "text": "A", "href": "/#faq"}]


def test_fetch_snapshot_returns_empty_for_unexpected_shape(monkeypatch):
    import io

    class _FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(request, timeout=0):
        return _FakeResponse(b'{"unexpected": true}')

    monkeypatch.setattr(company_knowledge.urllib.request, "urlopen", _fake_urlopen)

    assert company_knowledge._fetch_snapshot() == []
