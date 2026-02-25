from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.config import get_settings
from core_api.db import get_db
from core_api.models import Scope, WorkerHeartbeat
from core_api.schemas import HeartbeatRequest, MessageResponse, WorkerStatusItem, WorkerStatusResponse

router = APIRouter(prefix="/api/v1/workers", tags=["workers"])


@router.post("/heartbeat", response_model=MessageResponse)
def worker_heartbeat(
    payload: HeartbeatRequest,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    _ = identity
    row = db.get(WorkerHeartbeat, payload.worker_id)
    now = datetime.now(timezone.utc)
    if row is None:
        row = WorkerHeartbeat(worker_id=payload.worker_id, last_seen_at=now, info=payload.info)
    else:
        row.last_seen_at = now
        row.info = payload.info
    db.add(row)
    db.commit()
    return MessageResponse(message="ok")


@router.get("/status", response_model=WorkerStatusResponse)
def workers_status(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> WorkerStatusResponse:
    _ = identity
    active_minutes = get_settings().health_worker_active_minutes
    active_after = datetime.now(timezone.utc) - timedelta(minutes=active_minutes)

    workers = db.execute(select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc())).scalars().all()
    items: list[WorkerStatusItem] = []
    for worker in workers:
        is_active = worker.last_seen_at >= active_after
        items.append(
            WorkerStatusItem(
                worker_id=worker.worker_id,
                last_seen_at=worker.last_seen_at,
                active=is_active,
                info=worker.info,
            )
        )

    return WorkerStatusResponse(any_active=any(x.active for x in items), workers=items)
