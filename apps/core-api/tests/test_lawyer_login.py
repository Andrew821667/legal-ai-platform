"""Одноразовая ссылка входа юриста: ядро гасит nonce ровно один раз.

Закрепляется: вторая попытка с тем же nonce — 409 (ссылка сработала один
раз, даже если сайт перезапустился); в базе — хэш nonce, не он сам;
просроченные строки подчищаются; гасить может только ключ администратора.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import LawyerLoginNonce, Scope
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_practice import _cleanup, _key


def test_link_is_consumed_once() -> None:
    names = [f"pytest.lawyer-login.admin.{uuid4().hex}", f"pytest.lawyer-login.bot.{uuid4().hex}"]
    admin = {"X-API-Key": _key(Scope.admin, names[0])}
    bot = {"X-API-Key": _key(Scope.bot, names[1])}
    client = TestClient(app)
    nonce, old = uuid4().hex, uuid4().hex
    db = SessionLocal()
    try:
        db.add(LawyerLoginNonce(nonce_hash=hashlib.sha256(old.encode()).hexdigest(), telegram_user_id=1,
                                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    finally:
        db.close()
    body = {"nonce": nonce, "telegram_user_id": 500500,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}
    try:
        assert client.post("/api/v1/lawyer/login-nonces", headers=bot, json=body).status_code == 403
        assert client.post("/api/v1/lawyer/login-nonces", headers=admin, json={**body, "nonce": "x"}).status_code == 422
        assert client.post("/api/v1/lawyer/login-nonces", headers=admin, json=body).status_code == 201
        again = client.post("/api/v1/lawyer/login-nonces", headers=admin, json=body)
        assert again.status_code == 409
        db = SessionLocal()
        try:
            hashes = set(db.scalars(select(LawyerLoginNonce.nonce_hash)))
            assert hashlib.sha256(nonce.encode()).hexdigest() in hashes and nonce not in hashes
            assert hashlib.sha256(old.encode()).hexdigest() not in hashes  # просроченная подчищена
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(LawyerLoginNonce).where(LawyerLoginNonce.telegram_user_id.in_([1, 500500])))
            db.commit()
        finally:
            db.close()
        _cleanup(names, None)
