from __future__ import annotations

from typing import Any

from contract_worker.core_client import CoreClient


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


def test_touch_job_posts_expected_payload(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_post(url: str, json: dict[str, Any], headers: dict[str, str], timeout: int) -> _FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("contract_worker.core_client.requests.post", _fake_post)

    client = CoreClient("http://core-api:8000", "worker-key", timeout=13)
    response = client.touch_job(
        "job-123",
        "worker-abc",
        note="processing",
        progress_pct=35,
    )

    assert isinstance(response, _FakeResponse)
    assert captured["url"] == "http://core-api:8000/api/v1/contract-jobs/job-123/touch"
    assert captured["json"] == {
        "worker_id": "worker-abc",
        "note": "processing",
        "progress_pct": 35,
    }
    assert captured["headers"]["X-API-Key"] == "worker-key"
    assert captured["timeout"] == 13
