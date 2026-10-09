from __future__ import annotations

import importlib.util
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError

import pytest

PATH = Path(__file__).resolve().parents[3] / "infra/scripts/channel_silence.py"
SPEC = importlib.util.spec_from_file_location("channel_silence", PATH)
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)


def _responses(monkeypatch, pages):
    calls = []

    def fetch(req, *, timeout):
        calls.append(req.full_url)
        assert req.get_header("X-api-key") == "test-key"
        assert timeout == 15
        return io.StringIO(json.dumps(pages[len(calls) - 1]))

    monkeypatch.setattr(monitor, "urlopen", fetch)
    return calls


def test_silence_uses_latest_delivery_not_future_schedule(monkeypatch):
    _responses(monkeypatch, [[
        {"publish_at": "2026-10-09T18:00:00+03:00", "posted_at": "2026-10-08T09:16:35+03:00"},
        {"publish_at": "2026-10-09T09:00:00+03:00", "posted_at": "2026-10-09T09:04:22+03:00"},
    ]])

    assert monitor.channel_silence_hours(
        "http://core", "test-key", now=datetime(2026, 10, 9, 8, 20, tzinfo=UTC)
    ) == 2


def test_silence_scans_all_pages(monkeypatch):
    calls = _responses(monkeypatch, [
        [{"posted_at": "2026-10-06T09:00:00+03:00"}] * 100,
        [{"posted_at": "2026-10-09T09:00:00+03:00"}],
    ])
    assert monitor.channel_silence_hours(
        "http://core/", "test-key", now=datetime(2026, 10, 9, 8, tzinfo=UTC)
    ) == 2
    assert calls[1].endswith("offset=100")


def test_silence_does_not_treat_plan_as_delivery(monkeypatch):
    _responses(monkeypatch, [[
        {"publish_at": "2026-10-09T09:00:00+03:00"},
        {"posted_at": "invalid"},
    ]])
    assert monitor.channel_silence_hours("http://core", "test-key") == -1


def test_silence_reports_real_gap(monkeypatch):
    _responses(monkeypatch, [[{"posted_at": "2026-10-08T09:00:00+03:00"}]])
    assert monitor.channel_silence_hours(
        "http://core", "test-key", now=datetime(2026, 10, 9, 8, tzinfo=UTC)
    ) == 26


def test_silence_does_not_clear_alert_on_network_failure(monkeypatch):
    def failed(*args, **kwargs):
        raise URLError("core unavailable")

    monkeypatch.setattr(monitor, "urlopen", failed)
    with pytest.raises(URLError):
        monitor.channel_silence_hours("http://core", "test-key")
