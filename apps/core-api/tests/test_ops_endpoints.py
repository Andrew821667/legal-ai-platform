from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete

import core_api.main as main_module
from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, Scope, WorkerHeartbeat
from core_api.security import generate_api_key, hash_api_key


def _create_api_key(scope: Scope, name: str) -> str:
    raw_key = generate_api_key()
    db = SessionLocal()
    try:
        db.add(
            ApiKey(
                key_hash=hash_api_key(raw_key),
                scope=scope,
                name=name,
                is_active=True,
            )
        )
        db.commit()
        cache.invalidate()
    finally:
        db.close()
    return raw_key


def _delete_api_key(name: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(ApiKey).where(ApiKey.name == name))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def test_health_detailed_is_public_infra_endpoint() -> None:
    client = TestClient(app)
    ok = client.get("/health/detailed")
    assert ok.status_code == 200
    body = ok.json()
    assert set(body.keys()) == {"status", "db_ok", "disk_usage_pct", "memory_usage_pct", "uptime_seconds"}
    assert isinstance(body["db_ok"], bool)
    assert body["status"] in {"ok", "degraded"}


def test_workers_status_shape_for_admin() -> None:
    client = TestClient(app)
    admin_name = "pytest.ops.workers"
    admin_key = _create_api_key(Scope.admin, admin_name)

    try:
        response = client.get("/api/v1/workers/status", headers={"X-API-Key": admin_key})
        assert response.status_code == 200
        body = response.json()
        assert "any_active" in body
        assert "workers" in body
        assert isinstance(body["any_active"], bool)
        assert isinstance(body["workers"], list)
    finally:
        _delete_api_key(admin_name)


def test_worker_activity_shape_for_admin() -> None:
    client = TestClient(app)
    admin_name = "pytest.ops.worker_activity"
    admin_key = _create_api_key(Scope.admin, admin_name)
    worker_id = "pytest-worker-activity"

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        db.add(WorkerHeartbeat(worker_id=worker_id, last_seen_at=now, info={"mode": "poll"}))
        db.commit()
    finally:
        db.close()

    try:
        response = client.get(
            f"/api/v1/workers/{worker_id}/activity",
            headers={"X-API-Key": admin_key},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["worker_id"] == worker_id
        assert isinstance(body["active"], bool)
        assert "last_seen_at" in body
        assert body["window_hours"] == 24
        assert isinstance(body["startup_events"], list)
        assert isinstance(body["action_counts"], list)
        assert isinstance(body["entries"], list)
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == worker_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key(admin_name)


def test_unhandled_exception_calls_telegram_alert(monkeypatch) -> None:
    calls: list[str] = []

    def fake_alert(text: str) -> None:
        calls.append(text)

    monkeypatch.setattr(main_module, "send_telegram_alert", fake_alert)

    path = "/_pytest_raise_500"
    if not any(getattr(route, "path", None) == path for route in app.router.routes):
        @app.get(path)  # type: ignore[misc]
        def _raise_500() -> dict[str, str]:
            raise RuntimeError("pytest boom")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(path)

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert calls
    assert "Legal AI Core API error on" in calls[0]
