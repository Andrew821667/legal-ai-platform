"""Такт ядра: сбой шага не обрывает остальные, отметка такта и её проверка снаружи."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from core_api import (
    agreement_reminders,
    anonymization,
    backup_health,
    client_reviews,
    core_tick,
    deletion_log,
    telegram_delivery,
    weekly_digest,
)
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import Scope, ServiceHealth

from test_client_archive import _cleanup, _key


def _set_tick(checked_at: datetime | None) -> None:
    db = SessionLocal()
    try:
        row = db.get(ServiceHealth, core_tick.TICK_KEY)
        if row is None:
            row = ServiceHealth(key=core_tick.TICK_KEY)
            db.add(row)
        row.checked_at = checked_at
        db.commit()
    finally:
        db.close()


def test_failed_step_does_not_stop_the_rest(monkeypatch) -> None:
    ran: list[str] = []

    def boom():
        raise RuntimeError("digest is broken")

    monkeypatch.setattr(telegram_delivery, "tick", lambda: {"health": {"ok": True}, "due": {}})
    monkeypatch.setattr(agreement_reminders, "process_due", lambda *a, **k: ran.append("reminders") or {})
    monkeypatch.setattr(client_reviews, "process_due", lambda *a, **k: ran.append("reviews") or {})
    monkeypatch.setattr(weekly_digest, "maybe_queue", boom)
    monkeypatch.setattr(deletion_log, "watch", lambda *a, **k: ran.append("deletions") or {})
    monkeypatch.setattr(backup_health, "check", lambda *a, **k: ran.append("backup") or {})
    monkeypatch.setattr(anonymization, "run", lambda *a, **k: ran.append("anonymized") or {})
    name = f"pytest.tick.{uuid4().hex}"
    key = _key(Scope.bot, name)
    try:
        response = TestClient(app).post("/api/v1/telegram/tick", headers={"X-API-Key": key})
        assert response.status_code == 200
        body = response.json()
        assert body["weekly_digest"] == {"error": "RuntimeError"}
        # Раньше исключение в сводке обрывало такт: удаления, бэкап и обезличивание не шли.
        assert ran == ["reminders", "reviews", "deletions", "backup", "anonymized"]
        db = SessionLocal()
        try:
            row = db.get(ServiceHealth, core_tick.TICK_KEY)
            assert row is not None and row.ok is False and row.last_error == "weekly_digest"
            assert core_tick.is_fresh(db)
        finally:
            db.close()
    finally:
        _cleanup([name], [])


def test_telegram_step_failure_counts_as_no_link(monkeypatch) -> None:
    def boom():
        raise ConnectionError("proxy")

    monkeypatch.setattr(telegram_delivery, "tick", boom)
    monkeypatch.setattr(weekly_digest, "maybe_queue", lambda *a, **k: {})
    monkeypatch.setattr(deletion_log, "watch", lambda *a, **k: {})
    monkeypatch.setattr(backup_health, "check", lambda *a, **k: {})
    monkeypatch.setattr(anonymization, "run", lambda *a, **k: {})
    name = f"pytest.tick.{uuid4().hex}"
    key = _key(Scope.bot, name)
    try:
        body = TestClient(app).post("/api/v1/telegram/tick", headers={"X-API-Key": key}).json()
        assert body["health"] == {"ok": False, "error": "ConnectionError"}
        assert body["agreement_reminders"] == {"skipped": "no_link"}
    finally:
        _cleanup([name], [])


def test_health_tick_shows_whether_the_tick_runs() -> None:
    client = TestClient(app)
    now = datetime.now(timezone.utc)
    _set_tick(now - timedelta(minutes=2))
    assert client.get("/health/tick").status_code == 200
    _set_tick(now - core_tick.STALE_AFTER - timedelta(minutes=1))
    response = client.get("/health/tick")
    assert response.status_code == 503 and response.json() == {"ok": False}
    _set_tick(None)
    assert client.get("/health/tick").status_code == 503
