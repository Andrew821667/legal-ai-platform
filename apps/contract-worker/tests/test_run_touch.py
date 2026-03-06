from __future__ import annotations

import concurrent.futures
from typing import Any

from contract_worker import run


class _FakeFuture:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)

    def result(self, timeout: float) -> Any:
        _ = timeout
        if not self._responses:
            raise concurrent.futures.TimeoutError()
        value = self._responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class _FakeTouchResponse:
    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self) -> None:
        self.touch_calls: list[dict[str, Any]] = []

    def touch_job(
        self,
        job_id: str,
        worker_id: str,
        note: str | None = None,
        progress_pct: int | None = None,
    ) -> _FakeTouchResponse:
        self.touch_calls.append(
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "note": note,
                "progress_pct": progress_pct,
            }
        )
        return _FakeTouchResponse()


def _patch_monotonic(monkeypatch, values: list[float]) -> None:
    state = {"idx": 0}

    def _monotonic() -> float:
        idx = state["idx"]
        state["idx"] += 1
        if idx < len(values):
            return values[idx]
        return values[-1]

    monkeypatch.setattr(run.time, "monotonic", _monotonic)


def test_wait_for_result_with_touch_returns_fast_result(monkeypatch) -> None:
    monkeypatch.setattr(run.settings, "job_timeout_seconds", 120)
    monkeypatch.setattr(run.settings, "job_touch_interval_seconds", 30)
    monkeypatch.setattr(run.settings, "worker_id", "worker-fast")
    monkeypatch.setattr(run, "_safe_heartbeat", lambda *_args, **_kwargs: None)
    _patch_monotonic(monkeypatch, [0.0, 0.1])

    client = _FakeClient()
    future = _FakeFuture([{"result_summary": "ok"}])
    payload = run._wait_for_result_with_touch(client, {"id": "job-fast"}, future)

    assert payload == {"result_summary": "ok"}
    assert client.touch_calls == []


def test_wait_for_result_with_touch_calls_touch_on_long_job(monkeypatch) -> None:
    monkeypatch.setattr(run.settings, "job_timeout_seconds", 120)
    monkeypatch.setattr(run.settings, "job_touch_interval_seconds", 30)
    monkeypatch.setattr(run.settings, "worker_id", "worker-touch")
    monkeypatch.setattr(run, "_safe_heartbeat", lambda *_args, **_kwargs: None)
    _patch_monotonic(monkeypatch, [0.0, 0.1, 31.0, 32.0])

    client = _FakeClient()
    future = _FakeFuture([concurrent.futures.TimeoutError(), {"result_summary": "done"}])
    payload = run._wait_for_result_with_touch(client, {"id": "job-touch"}, future)

    assert payload == {"result_summary": "done"}
    assert len(client.touch_calls) == 1
    assert client.touch_calls[0]["job_id"] == "job-touch"
    assert client.touch_calls[0]["worker_id"] == "worker-touch"
    assert client.touch_calls[0]["note"] == "processing"


def test_wait_for_result_with_touch_returns_none_on_timeout(monkeypatch) -> None:
    monkeypatch.setattr(run.settings, "job_timeout_seconds", 60)
    monkeypatch.setattr(run.settings, "job_touch_interval_seconds", 30)
    monkeypatch.setattr(run.settings, "worker_id", "worker-timeout")
    monkeypatch.setattr(run, "_safe_heartbeat", lambda *_args, **_kwargs: None)
    _patch_monotonic(monkeypatch, [0.0, 0.1, 31.0, 61.0])

    client = _FakeClient()
    future = _FakeFuture([concurrent.futures.TimeoutError(), concurrent.futures.TimeoutError()])
    payload = run._wait_for_result_with_touch(client, {"id": "job-timeout"}, future)

    assert payload is None
    assert len(client.touch_calls) >= 1
