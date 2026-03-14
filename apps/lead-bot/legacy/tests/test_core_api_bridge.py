import json


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
