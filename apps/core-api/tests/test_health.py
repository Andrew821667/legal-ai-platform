from __future__ import annotations

from fastapi.testclient import TestClient

from core_api.main import app


def test_health_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
