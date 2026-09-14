from __future__ import annotations

from uuid import uuid4

from core_api.auth import cache
from core_api.client_notices import queue_notice
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, ClientNotice, Scope
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete


def test_notice_is_deduplicated_claimed_and_acknowledged_once() -> None:
    name = f"pytest.client-notice.{uuid4().hex}"
    event_key = f"act.accepted:{uuid4()}"
    raw = generate_api_key()
    db = SessionLocal()
    try:
        db.add(ApiKey(key_hash=hash_api_key(raw), scope=Scope.bot, name=name, is_active=True))
        queue_notice(db, event_key, "Клиент принял акт", "act:open:123")
        queue_notice(db, event_key, "Дубликат", None)
        db.commit()
        cache.invalidate()
    finally:
        db.close()

    client = TestClient(app)
    headers = {"X-API-Key": raw}
    try:
        claimed = client.post("/api/v1/client-notices/claim", headers=headers)
        assert claimed.status_code == 200
        mine = [row for row in claimed.json() if row["text"] == "Клиент принял акт"]
        assert len(mine) == 1
        assert mine[0]["callback_data"] == "act:open:123"
        assert client.post("/api/v1/client-notices/claim", headers=headers).json() == []

        bad = client.post(
            f"/api/v1/client-notices/{mine[0]['id']}/ack",
            headers=headers,
            json={"claim_token": str(uuid4())},
        )
        assert bad.status_code == 409
        done = client.post(
            f"/api/v1/client-notices/{mine[0]['id']}/ack",
            headers=headers,
            json={"claim_token": mine[0]["claim_token"]},
        )
        assert done.status_code == 200
        assert done.json() == {"delivered": True}
        assert client.post("/api/v1/client-notices/claim", headers=headers).json() == []
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ClientNotice).where(ClientNotice.event_key == event_key))
            db.execute(delete(ApiKey).where(ApiKey.name == name))
            db.commit()
            cache.invalidate()
        finally:
            db.close()
