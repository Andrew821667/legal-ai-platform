import json
import urllib.error


def _enable_bridge(monkeypatch, bridge_module):
    monkeypatch.setattr(bridge_module.config, "CORE_API_URL", "http://core-api:8000")
    monkeypatch.setattr(bridge_module.config, "API_KEY_BOT", "test-api-key")
    monkeypatch.setattr(bridge_module.config, "CORE_API_SYNC_ENABLED", True)
    monkeypatch.setattr(bridge_module.config, "CORE_API_TIMEOUT_SECONDS", 5.0)
    monkeypatch.setattr(bridge_module.config, "CORE_API_POST_DEDUP_TTL_SECONDS", 30.0)


class _FakeResponse:
    def __init__(self, body: dict):
        self._body = body

    def read(self):
        return json.dumps(self._body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_verify_returning_client_returns_telegram_id_when_verified(monkeypatch):
    import core_api_bridge as bridge_module

    _enable_bridge(monkeypatch, bridge_module)
    captured = {}

    def _fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"verified": True, "telegram_user_id": 72001})

    monkeypatch.setattr(bridge_module.urllib.request, "urlopen", _fake_urlopen)

    bridge = bridge_module.CoreApiBridge()
    result = bridge.verify_returning_client(contact="+7 909 233-09-09", agreement_number="P-001")

    assert result == 72001
    assert captured["url"] == "http://core-api:8000/api/v1/client-portal/verify"
    assert captured["body"] == {"contact": "+7 909 233-09-09", "agreement_number": "P-001"}


def test_verify_returning_client_returns_none_when_not_verified(monkeypatch):
    import core_api_bridge as bridge_module

    _enable_bridge(monkeypatch, bridge_module)
    monkeypatch.setattr(
        bridge_module.urllib.request,
        "urlopen",
        lambda request, timeout=0: _FakeResponse({"verified": False}),
    )

    bridge = bridge_module.CoreApiBridge()
    result = bridge.verify_returning_client(contact="+79990000000", agreement_number="P-999")

    assert result is None


def test_verify_returning_client_returns_none_when_disabled(monkeypatch):
    import core_api_bridge as bridge_module

    monkeypatch.setattr(bridge_module.config, "CORE_API_SYNC_ENABLED", False)

    def _fail_if_called(request, timeout=0):
        raise AssertionError("must not call core-api when bridge is disabled")

    monkeypatch.setattr(bridge_module.urllib.request, "urlopen", _fail_if_called)

    bridge = bridge_module.CoreApiBridge()
    result = bridge.verify_returning_client(contact="+79990000000", agreement_number="P-001")

    assert result is None


def test_verify_returning_client_returns_none_on_http_error(monkeypatch):
    import core_api_bridge as bridge_module

    _enable_bridge(monkeypatch, bridge_module)

    def _raise(request, timeout=0):
        raise urllib.error.HTTPError("url", 500, "Internal Server Error", {}, None)

    monkeypatch.setattr(bridge_module.urllib.request, "urlopen", _raise)

    bridge = bridge_module.CoreApiBridge()
    result = bridge.verify_returning_client(contact="+79990000000", agreement_number="P-001")

    assert result is None


def test_core_api_bridge_skips_recent_duplicate_posts(monkeypatch):
    import core_api_bridge as bridge_module

    monkeypatch.setattr(bridge_module.config, "CORE_API_URL", "http://core-api:8000")
    monkeypatch.setattr(bridge_module.config, "API_KEY_BOT", "test-api-key")
    monkeypatch.setattr(bridge_module.config, "CORE_API_SYNC_ENABLED", True)
    monkeypatch.setattr(bridge_module.config, "CORE_API_TIMEOUT_SECONDS", 5.0)
    monkeypatch.setattr(bridge_module.config, "CORE_API_POST_DEDUP_TTL_SECONDS", 30.0)

    calls = {"count": 0}

    class _FakeResponse:
        def read(self):
            return json.dumps({"id": "user-core-id"}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(request, timeout=0):
        calls["count"] += 1
        return _FakeResponse()

    monkeypatch.setattr(bridge_module.urllib.request, "urlopen", _fake_urlopen)

    bridge = bridge_module.CoreApiBridge()
    payload = {"telegram_id": 123, "name": "Cached User"}

    result_first = bridge._post("/api/v1/users", payload, idempotency_key="same-key")
    result_second = bridge._post("/api/v1/users", payload, idempotency_key="same-key")

    assert result_first == {"id": "user-core-id"}
    assert result_second is None
    assert calls["count"] == 1
