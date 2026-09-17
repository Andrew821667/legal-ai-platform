"""KnowledgeEngine: клиент эмбеддингов должен идти на OpenAI, а не наследовать
общий DeepSeek base_url чата бота — регрессия на баг 16.09 (404 на каждый
запрос эмбеддинга, RAG по диалогам молча не работал)."""
import knowledge_engine


def test_knowledge_engine_uses_dedicated_embedding_base_url(monkeypatch):
    monkeypatch.setattr(knowledge_engine.config, "OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setattr(knowledge_engine.config, "EMBEDDING_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(knowledge_engine.config, "EMBEDDING_MODEL", "text-embedding-3-small")

    engine = knowledge_engine.KnowledgeEngine()

    assert str(engine.client.base_url).rstrip("/") == "https://api.openai.com/v1"
    assert engine.embedding_model == "text-embedding-3-small"


def test_knowledge_engine_does_not_use_chat_base_url(monkeypatch):
    """Явная регрессия: даже если OPENAI_BASE_URL пуст/иной, эмбеддинг-клиент
    не должен на него ориентироваться вовсе — только на EMBEDDING_BASE_URL."""
    monkeypatch.setattr(knowledge_engine.config, "OPENAI_BASE_URL", "https://example-chat-provider.test/v1")
    monkeypatch.setattr(knowledge_engine.config, "EMBEDDING_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(knowledge_engine.config, "EMBEDDING_MODEL", "text-embedding-3-small")

    engine = knowledge_engine.KnowledgeEngine()

    assert "example-chat-provider" not in str(engine.client.base_url)


def test_knowledge_engine_respects_custom_embedding_model(monkeypatch):
    monkeypatch.setattr(knowledge_engine.config, "EMBEDDING_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(knowledge_engine.config, "EMBEDDING_MODEL", "text-embedding-3-large")

    engine = knowledge_engine.KnowledgeEngine()

    assert engine.embedding_model == "text-embedding-3-large"


def test_knowledge_engine_routes_through_configured_proxy(monkeypatch):
    """С прод-хоста OpenAI отвечает 403 unsupported_country_region_territory
    без прокси (обнаружено 17.09 живым тестом бота) — эмбеддинг-клиент должен
    заворачиваться через EMBEDDING_PROXY_URL, когда он задан."""
    monkeypatch.setattr(knowledge_engine.config, "EMBEDDING_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(knowledge_engine.config, "EMBEDDING_PROXY_URL", "http://host.docker.internal:11808")

    # Подменять httpx.Client голой функцией нельзя: openai сам делает
    # isinstance(http_client, httpx.Client) внутри, и без настоящего класса
    # падает с "isinstance() arg 2 must be a type". Наследник — по-прежнему
    # httpx.Client, isinstance проходит, а kwargs всё равно видно.
    captured_kwargs = {}

    class SpyClient(knowledge_engine.httpx.Client):
        def __init__(self, *args, **kwargs):
            captured_kwargs.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(knowledge_engine.httpx, "Client", SpyClient)

    knowledge_engine.KnowledgeEngine()

    assert captured_kwargs.get("proxy") == "http://host.docker.internal:11808"


def test_knowledge_engine_no_proxy_client_when_unconfigured(monkeypatch):
    """Без EMBEDDING_PROXY_URL (дев-окружения, CI) поведение не меняется —
    отдельный httpx.Client вообще не создаётся, клиент как раньше."""
    monkeypatch.setattr(knowledge_engine.config, "EMBEDDING_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(knowledge_engine.config, "EMBEDDING_PROXY_URL", "")

    calls = []
    monkeypatch.setattr(knowledge_engine.httpx, "Client", lambda *a, **k: calls.append((a, k)))

    knowledge_engine.KnowledgeEngine()

    assert calls == []
