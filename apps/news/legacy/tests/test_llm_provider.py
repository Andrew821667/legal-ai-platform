import asyncio
from types import SimpleNamespace

from app.modules.llm_provider import LLMProvider


class _StubResponse:
    def __init__(self, content: str) -> None:
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]
        self.usage = SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)


class _StubCompletions:
    async def create(self, **kwargs):
        return _StubResponse("Готовый weekly summary")


class _StubChat:
    def __init__(self) -> None:
        self.completions = _StubCompletions()


class _StubAsyncOpenAI:
    def __init__(self, **kwargs) -> None:
        self.chat = _StubChat()


class _StubDB:
    def __init__(self) -> None:
        self.rollback_called = False

    async def rollback(self) -> None:
        self.rollback_called = True


def test_deepseek_completion_survives_usage_tracking_failure(monkeypatch) -> None:
    async def _boom(**kwargs):
        raise RuntimeError("api_usage relation missing")

    monkeypatch.setattr("app.modules.llm_provider.AsyncOpenAI", _StubAsyncOpenAI)
    monkeypatch.setattr("app.modules.api_usage_tracker.track_api_usage", _boom)
    monkeypatch.setattr("app.modules.llm_provider.settings.deepseek_api_key", "sk-test", raising=False)
    monkeypatch.setattr("app.modules.llm_provider.settings.deepseek_base_url", "https://api.deepseek.com/v1", raising=False)
    monkeypatch.setattr("app.modules.llm_provider.settings.deepseek_model", "deepseek-chat", raising=False)
    monkeypatch.setattr("app.modules.llm_provider.settings.openai_base_url", "", raising=False)
    monkeypatch.setattr("app.modules.llm_provider.settings.news_model", "", raising=False)

    provider = LLMProvider("deepseek")
    db = _StubDB()
    result = asyncio.run(
        provider._generate_deepseek(
            messages=[{"role": "user", "content": "test"}],
            operation="reader_weekly_digest",
            db=db,
        )
    )

    assert result == "Готовый weekly summary"
    assert db.rollback_called is True
