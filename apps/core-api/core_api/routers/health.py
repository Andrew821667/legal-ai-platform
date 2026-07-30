from __future__ import annotations

from datetime import datetime, timezone

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from core_api.auth import get_api_key_identity
from core_api.db import get_db
from core_api.models import Scope

router = APIRouter(tags=["health"])


def _has_ops_scope(request: Request, db: Session) -> bool:
    """Проверяет ops-ключ, не отклоняя запрос без него.

    Эндпоинт остаётся публичным для внешних проверок доступности, поэтому
    отсутствие или невалидность ключа не ошибка — просто ответ будет урезан.
    """
    if not request.headers.get("X-API-Key"):
        return False
    try:
        identity = get_api_key_identity(request, db)
    except HTTPException:
        return False
    return identity.scope in (Scope.worker, Scope.admin)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/detailed")
def health_detailed(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, float | bool | str]:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    status = "ok" if db_ok else "degraded"
    payload: dict[str, float | bool | str] = {"status": status, "db_ok": db_ok}

    # Загрузка диска, памяти и аптайм — сведения о самом хосте: они подсказывают
    # атакующему момент, когда сервер близок к исчерпанию ресурсов, и облегчают
    # выбор времени для DoS. Отдаём их только по ключу worker/admin, а сам
    # эндпоинт оставляем публичным, чтобы не ломать внешние проверки живости.
    if _has_ops_scope(request, db):
        disk = psutil.disk_usage("/")
        memory = psutil.virtual_memory()
        started_at = getattr(request.app.state, "started_at", datetime.now(timezone.utc))
        payload["disk_usage_pct"] = round(disk.percent, 2)
        payload["memory_usage_pct"] = round(memory.percent, 2)
        payload["uptime_seconds"] = int((datetime.now(timezone.utc) - started_at).total_seconds())

    return payload
