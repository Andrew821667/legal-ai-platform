from __future__ import annotations

from datetime import datetime, timezone

import psutil
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from core_api.db import get_db

router = APIRouter(tags=["health"])


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

    disk = psutil.disk_usage("/")
    memory = psutil.virtual_memory()
    started_at = getattr(request.app.state, "started_at", datetime.now(timezone.utc))
    uptime_seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())
    status = "ok" if db_ok else "degraded"

    return {
        "status": status,
        "db_ok": db_ok,
        "disk_usage_pct": round(disk.percent, 2),
        "memory_usage_pct": round(memory.percent, 2),
        "uptime_seconds": uptime_seconds,
    }
