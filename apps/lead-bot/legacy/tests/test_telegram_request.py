from __future__ import annotations

import bot


def test_telegram_request_uses_platform_balancer(monkeypatch) -> None:
    captured = {}

    def request(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(bot.config, "TELEGRAM_API_PROXY_URL", "http://192.168.64.1:10811")
    monkeypatch.setattr(bot, "HTTPXRequest", request)

    result = bot._telegram_request(read_timeout=45.0)

    assert result is not None
    assert captured["proxy"] == "http://192.168.64.1:10811"
    assert captured["read_timeout"] == 45.0
