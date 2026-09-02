from news.admin_bot import (
    POLL_READ_TIMEOUT_SECONDS,
    POLL_TIMEOUT_SECONDS,
    _application_builder,
    _telegram_request,
)
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
    monkeypatch.setattr(
        "news.admin_bot._telegram_request", lambda _proxy, **_kwargs: next(requests)
    )
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


def test_get_updates_request_allows_for_long_polling_duration() -> None:
    """У опроса обновлений запас по чтению больше, чем у обычных вызовов.

    getUpdates держит соединение открытым всю длительность long polling.
    Если read_timeout не превышает её, клиент разрывает исправное соединение
    сам и порождает поток ложных TimedOut.
    """
    proxy_url = "http://192.168.64.1:10811"

    regular = _telegram_request(proxy_url)
    polling = _telegram_request(proxy_url, read_timeout=POLL_READ_TIMEOUT_SECONDS)

    assert POLL_READ_TIMEOUT_SECONDS > POLL_TIMEOUT_SECONDS
    assert polling.read_timeout > regular.read_timeout
    assert polling.read_timeout >= POLL_TIMEOUT_SECONDS + 10


def test_application_builder_gives_polling_its_own_timeout(monkeypatch) -> None:
    """Обычные вызовы и getUpdates получают разные экземпляры запроса."""
    builder = _Builder()
    captured: list[float] = []

    def _fake_request(_proxy, *, read_timeout=20.0):
        captured.append(read_timeout)
        return object()

    monkeypatch.setattr("news.admin_bot.Application.builder", lambda: builder)
    monkeypatch.setattr("news.admin_bot._telegram_request", _fake_request)
    monkeypatch.setattr(settings, "telegram_api_proxy_url", "http://192.168.64.1:10811")

    _application_builder("test-token")

    assert len(captured) == 2
    assert captured[1] > captured[0]
