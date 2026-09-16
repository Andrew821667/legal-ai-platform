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
