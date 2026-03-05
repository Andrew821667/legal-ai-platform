from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.config import get_settings
from core_api.db import get_db
from core_api.models import Scope, WorkerActivity, WorkerHeartbeat
from core_api.schemas import (
    HeartbeatRequest,
    MessageResponse,
    WorkerActionCount,
    WorkerActivityEntry,
    WorkerActivityResponse,
    WorkerStatusItem,
    WorkerStatusResponse,
)

router = APIRouter(prefix="/api/v1/workers", tags=["workers"])


@router.post("/heartbeat", response_model=MessageResponse)
def worker_heartbeat(
    payload: HeartbeatRequest,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.news, Scope.admin)),
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
    action = str((payload.info or {}).get("action") or "").strip()
    if action:
        try:
            activity = WorkerActivity(
                worker_id=payload.worker_id,
                occurred_at=now,
                action=action[:120],
                details=payload.info,
            )
            db.add(activity)
            db.commit()
        except ProgrammingError:
            # Graceful fallback during rolling deploy before migration is applied.
            db.rollback()
    return MessageResponse(message="ok")


@router.get("/status", response_model=WorkerStatusResponse)
def workers_status(
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.news, Scope.admin)),
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


@router.get("/{worker_id}/activity", response_model=WorkerActivityResponse)
def worker_activity(
    worker_id: str,
    hours: int = 24,
    limit: int = 30,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.news, Scope.admin)),
    db: Session = Depends(get_db),
) -> WorkerActivityResponse:
    _ = identity
    window_hours = max(1, min(int(hours), 168))
    row_limit = max(1, min(int(limit), 200))
    now = datetime.now(timezone.utc)
    active_minutes = get_settings().health_worker_active_minutes
    active_after = now - timedelta(minutes=active_minutes)
    start_after = now - timedelta(hours=window_hours)

    heartbeat = db.get(WorkerHeartbeat, worker_id)

    action_counts: list[WorkerActionCount] = []
    startup_rows: list[datetime] = []
    entries: list[WorkerActivityEntry] = []
    try:
        action_counts_rows = db.execute(
            select(WorkerActivity.action, func.count())
            .where(
                WorkerActivity.worker_id == worker_id,
                WorkerActivity.occurred_at >= start_after,
            )
            .group_by(WorkerActivity.action)
            .order_by(func.count().desc(), WorkerActivity.action.asc())
        ).all()
        action_counts = [WorkerActionCount(action=str(action), count=int(count)) for action, count in action_counts_rows]

        startup_rows = list(
            db.execute(
                select(WorkerActivity.occurred_at)
                .where(
                    WorkerActivity.worker_id == worker_id,
                    WorkerActivity.action == "startup",
                    WorkerActivity.occurred_at >= start_after,
                )
                .order_by(WorkerActivity.occurred_at.desc())
                .limit(20)
            ).scalars().all()
        )

        recent_rows = db.execute(
            select(WorkerActivity)
            .where(
                WorkerActivity.worker_id == worker_id,
                WorkerActivity.occurred_at >= start_after,
            )
            .order_by(WorkerActivity.occurred_at.desc())
            .limit(row_limit)
        ).scalars().all()
        entries = [
            WorkerActivityEntry(
                occurred_at=item.occurred_at,
                action=item.action,
                details=item.details,
            )
            for item in recent_rows
        ]
    except ProgrammingError:
        db.rollback()

    last_seen = heartbeat.last_seen_at if heartbeat else None
    active = bool(last_seen and last_seen >= active_after)
    return WorkerActivityResponse(
        worker_id=worker_id,
        active=active,
        last_seen_at=last_seen,
        window_hours=window_hours,
        startup_events=list(startup_rows),
        action_counts=action_counts,
        entries=entries,
    )
