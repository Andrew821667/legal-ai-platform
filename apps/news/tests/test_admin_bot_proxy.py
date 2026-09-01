from news.admin_bot import _application_builder
from news.settings import settings


class _Builder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def token(self, value: str):
        self.calls.append(("token", value))
        return self

    def proxy(self, value: str):
        self.calls.append(("proxy", value))
        return self

    def get_updates_proxy(self, value: str):
        self.calls.append(("get_updates_proxy", value))
        return self


def test_application_builder_uses_telegram_proxy(monkeypatch) -> None:
    builder = _Builder()
    proxy_url = "http://192.168.64.1:10811"
    monkeypatch.setattr("news.admin_bot.Application.builder", lambda: builder)
    monkeypatch.setattr(settings, "telegram_api_proxy_url", proxy_url)

    assert _application_builder("test-token") is builder
    assert builder.calls == [
        ("token", "test-token"),
        ("proxy", proxy_url),
        ("get_updates_proxy", proxy_url),
    ]


def test_application_builder_keeps_direct_mode_without_proxy(monkeypatch) -> None:
    builder = _Builder()
    monkeypatch.setattr("news.admin_bot.Application.builder", lambda: builder)
    monkeypatch.setattr(settings, "telegram_api_proxy_url", "")

    assert _application_builder("test-token") is builder
    assert builder.calls == [("token", "test-token")]
