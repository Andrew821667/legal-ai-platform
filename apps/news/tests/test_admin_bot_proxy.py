from news.admin_bot import _application_builder, _telegram_request
from news.settings import settings


class _Builder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def token(self, value: str):
        self.calls.append(("token", value))
        return self

    def request(self, value):
        self.calls.append(("request", value))
        return self

    def get_updates_request(self, value):
        self.calls.append(("get_updates_request", value))
        return self


def test_application_builder_uses_telegram_proxy(monkeypatch) -> None:
    builder = _Builder()
    proxy_url = "http://192.168.64.1:10811"
    request = object()
    updates_request = object()
    requests = iter((request, updates_request))
    monkeypatch.setattr("news.admin_bot.Application.builder", lambda: builder)
    monkeypatch.setattr("news.admin_bot._telegram_request", lambda _proxy: next(requests))
    monkeypatch.setattr(settings, "telegram_api_proxy_url", proxy_url)

    assert _application_builder("test-token") is builder
    assert builder.calls == [
        ("token", "test-token"),
        ("request", request),
        ("get_updates_request", updates_request),
    ]


def test_application_builder_keeps_direct_mode_without_proxy(monkeypatch) -> None:
    builder = _Builder()
    monkeypatch.setattr("news.admin_bot.Application.builder", lambda: builder)
    monkeypatch.setattr(settings, "telegram_api_proxy_url", "")

    assert _application_builder("test-token") is builder
    assert builder.calls == [("token", "test-token")]


def test_telegram_proxy_request_disables_keepalive() -> None:
    request = _telegram_request("http://192.168.64.1:10811")

    limits = request._client_kwargs["limits"]
    assert limits.max_connections == 16
    assert limits.max_keepalive_connections == 0
    assert request.read_timeout == 20.0
