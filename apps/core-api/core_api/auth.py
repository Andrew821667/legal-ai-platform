from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.config import get_settings
from core_api.db import get_db
from core_api.models import ApiKey, Scope
from core_api.security import verify_api_key


@dataclass
class ApiKeyIdentity:
    id: uuid.UUID
    scope: Scope
    name: str


class ActiveApiKeyCache:
    def __init__(self) -> None:
        self._items: list[ApiKey] = []
        self._last_refresh: float = 0.0
        self._lock = threading.Lock()

    def _needs_refresh(self) -> bool:
        ttl = get_settings().api_key_cache_ttl_seconds
        return time.time() - self._last_refresh > ttl

    def get_items(self, db: Session) -> list[ApiKey]:
        if self._needs_refresh():
            with self._lock:
                if self._needs_refresh():
                    self._items = db.execute(select(ApiKey).where(ApiKey.is_active.is_(True))).scalars().all()
                    self._last_refresh = time.time()
        return self._items

    def invalidate(self) -> None:
        with self._lock:
            self._last_refresh = 0.0


cache = ActiveApiKeyCache()


def _forbidden(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def get_api_key_identity(request: Request, db: Session = Depends(get_db)) -> ApiKeyIdentity:
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key")

    active_keys = cache.get_items(db)
    for row in active_keys:
        if verify_api_key(raw_key, row.key_hash):
            row.last_used_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            return ApiKeyIdentity(id=row.id, scope=row.scope, name=row.name)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def require_scopes(*allowed: Scope):
    def dependency(identity: ApiKeyIdentity = Depends(get_api_key_identity)) -> ApiKeyIdentity:
        if identity.scope not in allowed and identity.scope != Scope.admin:
            raise _forbidden("Insufficient scope")
        return identity

    return dependency
