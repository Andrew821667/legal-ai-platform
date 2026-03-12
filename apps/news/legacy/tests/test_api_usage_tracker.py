import asyncio

from app.modules import api_usage_tracker
from app.modules.api_usage_tracker import track_api_usage


class _MissingTablesResult:
    def mappings(self):
        return self

    def one(self):
        return {
            "has_api_usage": False,
            "has_monthly_api_stats": False,
        }


class _StubDB:
    def __init__(self) -> None:
        self.add_called = False
        self.commit_called = False
        self.execute_called = 0

    async def execute(self, stmt):
        self.execute_called += 1
        return _MissingTablesResult()

    def add(self, obj) -> None:
        self.add_called = True

    async def commit(self) -> None:
        self.commit_called = True


def test_track_api_usage_skips_when_analytics_tables_absent(monkeypatch) -> None:
    monkeypatch.setattr(api_usage_tracker, "_usage_tracking_schema_available", None)

    db = _StubDB()
    result = asyncio.run(
        track_api_usage(
            db=db,
            provider="deepseek",
            model="deepseek-chat",
            operation="reader_weekly_digest",
            prompt_tokens=10,
            completion_tokens=5,
        )
    )

    assert result is None
    assert db.execute_called == 1
    assert db.add_called is False
    assert db.commit_called is False
