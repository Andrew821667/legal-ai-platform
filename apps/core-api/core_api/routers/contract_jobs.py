from __future__ import annotations

import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import ActorType, AuditLog, ContractJob, ContractJobStatus, Scope
from core_api.schemas import (
    ClaimRequest,
    ContractJobBulkRetryOut,
    ContractJobCreate,
    ContractJobFinalizeExhaustedOut,
    ContractJobMaintenanceActionOut,
    ContractJobMaintenanceOut,
    ContractJobOpsActionCount,
    ContractJobOpsEventEntry,
    ContractJobOpsOverviewOut,
    ContractJobOpsSampleItem,
    ContractJobOpsSamples,
    ContractJobHistoryEntry,
    ContractJobHistoryResponse,
    ContractJobOut,
    ContractJobPatch,
    ContractJobResult,
    ContractJobTouch,
    ContractJobSummaryOut,
)

router = APIRouter(prefix="/api/v1/contract-jobs", tags=["contract-jobs"])


def _apply_contract_job_filters(
    stmt: Any,
    *,
    now: datetime,
    status: ContractJobStatus | None,
    lead_id: uuid.UUID | None,
    worker_id: str | None,
    stale_processing_only: bool,
    stale_minutes: int,
    failed_retryable_only: bool,
    new_retryable_only: bool,
    new_older_than_minutes: int | None,
) -> Any:
    if status:
        stmt = stmt.where(ContractJob.status == status)
    if lead_id:
        stmt = stmt.where(ContractJob.lead_id == lead_id)
    if worker_id:
        stmt = stmt.where(ContractJob.worker_id == worker_id)
    if stale_processing_only:
        stmt = stmt.where(
            ContractJob.status == ContractJobStatus.processing,
            ContractJob.updated_at < (now - timedelta(minutes=stale_minutes)),
        )
    if failed_retryable_only:
        stmt = stmt.where(
            ContractJob.status == ContractJobStatus.failed,
            ContractJob.attempts < ContractJob.max_attempts,
        )
    if new_retryable_only:
        stmt = stmt.where(
            ContractJob.status == ContractJobStatus.new,
            ContractJob.attempts < ContractJob.max_attempts,
        )
    if new_older_than_minutes is not None:
        stmt = stmt.where(
            ContractJob.status == ContractJobStatus.new,
            ContractJob.created_at < (now - timedelta(minutes=new_older_than_minutes)),
        )
    return stmt


def _build_contract_job_summary(
    db: Session,
    *,
    now: datetime,
    window_hours: int,
    stale_minutes: int,
) -> ContractJobSummaryOut:
    stale_before = now - timedelta(minutes=stale_minutes)
    window_start = now - timedelta(hours=window_hours)

    total = int(db.execute(select(func.count()).select_from(ContractJob)).scalar_one())
    status_rows = db.execute(select(ContractJob.status, func.count()).group_by(ContractJob.status)).all()
    by_status = {status.value: 0 for status in ContractJobStatus}
    for status, count in status_rows:
        by_status[status.value] = int(count)

    processing_stale_count = int(
        db.execute(
            select(func.count())
            .select_from(ContractJob)
            .where(
                ContractJob.status == ContractJobStatus.processing,
                ContractJob.updated_at < stale_before,
            )
        ).scalar_one()
    )
    failed_retryable_count = int(
        db.execute(
            select(func.count())
            .select_from(ContractJob)
            .where(
                ContractJob.status == ContractJobStatus.failed,
                ContractJob.attempts < ContractJob.max_attempts,
            )
        ).scalar_one()
    )
    failed_terminal_count = int(
        db.execute(
            select(func.count())
            .select_from(ContractJob)
            .where(
                ContractJob.status == ContractJobStatus.failed,
                ContractJob.attempts >= ContractJob.max_attempts,
            )
        ).scalar_one()
    )
    oldest_new_created_at = db.execute(
        select(func.min(ContractJob.created_at)).where(ContractJob.status == ContractJobStatus.new)
    ).scalar_one()
    oldest_new_age_minutes: int | None = None
    if oldest_new_created_at is not None:
        oldest_new_age_minutes = max(
            int((now - oldest_new_created_at).total_seconds() // 60),
            0,
        )

    done_last_hours_count = int(
        db.execute(
            select(func.count())
            .select_from(ContractJob)
            .where(
                ContractJob.status == ContractJobStatus.done,
                ContractJob.updated_at >= window_start,
            )
        ).scalar_one()
    )
    new_retryable_count = int(
        db.execute(
            select(func.count())
            .select_from(ContractJob)
            .where(
                ContractJob.status == ContractJobStatus.new,
                ContractJob.attempts < ContractJob.max_attempts,
            )
        ).scalar_one()
    )
    new_exhausted_count = int(
        db.execute(
            select(func.count())
            .select_from(ContractJob)
            .where(
                ContractJob.status == ContractJobStatus.new,
                ContractJob.attempts >= ContractJob.max_attempts,
            )
        ).scalar_one()
    )

    return ContractJobSummaryOut(
        total=total,
        by_status=by_status,
        new_retryable_count=new_retryable_count,
        new_exhausted_count=new_exhausted_count,
        processing_stale_count=processing_stale_count,
        failed_retryable_count=failed_retryable_count,
        failed_terminal_count=failed_terminal_count,
        new_oldest_created_at=oldest_new_created_at,
        new_oldest_age_minutes=oldest_new_age_minutes,
        done_last_hours_count=done_last_hours_count,
        window_hours=window_hours,
        stale_minutes=stale_minutes,
    )


@router.post("", response_model=ContractJobOut)
def create_contract_job(
    payload: ContractJobCreate,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJob:
    _ = identity
    job = ContractJob(**payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=None)
def list_contract_jobs(
    status: ContractJobStatus | None = Query(default=None),
    lead_id: uuid.UUID | None = Query(default=None),
    worker_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0, le=100000),
    limit: int = Query(default=20, ge=1, le=100),
    order_by: Literal["priority", "created_at", "updated_at", "deadline_at"] = Query(default="priority"),
    order_dir: Literal["asc", "desc"] = Query(default="asc"),
    stale_processing_only: bool = Query(default=False),
    stale_minutes: int = Query(default=30, ge=1, le=240),
    failed_retryable_only: bool = Query(default=False),
    new_retryable_only: bool = Query(default=False),
    new_older_than_minutes: int | None = Query(default=None, ge=1, le=10080),
    count_only: bool = Query(default=False),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> Any:
    _ = identity
    now = datetime.now(timezone.utc)
    if count_only:
        stmt = select(func.count()).select_from(ContractJob)
        stmt = _apply_contract_job_filters(
            stmt,
            now=now,
            status=status,
            lead_id=lead_id,
            worker_id=worker_id,
            stale_processing_only=stale_processing_only,
            stale_minutes=stale_minutes,
            failed_retryable_only=failed_retryable_only,
            new_retryable_only=new_retryable_only,
            new_older_than_minutes=new_older_than_minutes,
        )
        count = db.execute(stmt).scalar_one()
        return {"count": count}

    stmt = select(ContractJob)
    stmt = _apply_contract_job_filters(
        stmt,
        now=now,
        status=status,
        lead_id=lead_id,
        worker_id=worker_id,
        stale_processing_only=stale_processing_only,
        stale_minutes=stale_minutes,
        failed_retryable_only=failed_retryable_only,
        new_retryable_only=new_retryable_only,
        new_older_than_minutes=new_older_than_minutes,
    )

    order_expr_map = {
        "priority": ContractJob.priority,
        "created_at": ContractJob.created_at,
        "updated_at": ContractJob.updated_at,
        "deadline_at": ContractJob.deadline_at,
    }
    primary_col = order_expr_map[order_by]
    primary_order = primary_col.asc() if order_dir == "asc" else primary_col.desc()
    if order_by == "deadline_at":
        primary_order = primary_order.nulls_last()

    stmt = stmt.order_by(primary_order, ContractJob.priority.asc(), ContractJob.created_at.asc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


@router.get("/summary", response_model=ContractJobSummaryOut)
def contract_jobs_summary(
    window_hours: int = Query(default=24, ge=1, le=168),
    stale_minutes: int = Query(default=30, ge=1, le=240),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJobSummaryOut:
    _ = identity
    now = datetime.now(timezone.utc)
    return _build_contract_job_summary(
        db,
        now=now,
        window_hours=window_hours,
        stale_minutes=stale_minutes,
    )


@router.get("/ops-overview", response_model=ContractJobOpsOverviewOut)
def contract_jobs_ops_overview(
    window_hours: int = Query(default=24, ge=1, le=168),
    stale_minutes: int = Query(default=30, ge=1, le=240),
    sample_limit: int = Query(default=10, ge=1, le=100),
    events_limit: int = Query(default=30, ge=1, le=200),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJobOpsOverviewOut:
    _ = identity
    now = datetime.now(timezone.utc)
    summary = _build_contract_job_summary(
        db,
        now=now,
        window_hours=window_hours,
        stale_minutes=stale_minutes,
    )
    stale_before = now - timedelta(minutes=stale_minutes)
    window_start = now - timedelta(hours=window_hours)

    stale_processing = list(
        db.execute(
            select(ContractJob)
            .where(
                ContractJob.status == ContractJobStatus.processing,
                ContractJob.updated_at < stale_before,
            )
            .order_by(ContractJob.updated_at.asc(), ContractJob.created_at.asc())
            .limit(sample_limit)
        ).scalars().all()
    )
    failed_retryable = list(
        db.execute(
            select(ContractJob)
            .where(
                ContractJob.status == ContractJobStatus.failed,
                ContractJob.attempts < ContractJob.max_attempts,
            )
            .order_by(ContractJob.updated_at.asc(), ContractJob.created_at.asc())
            .limit(sample_limit)
        ).scalars().all()
    )
    new_exhausted = list(
        db.execute(
            select(ContractJob)
            .where(
                ContractJob.status == ContractJobStatus.new,
                ContractJob.attempts >= ContractJob.max_attempts,
            )
            .order_by(ContractJob.updated_at.asc(), ContractJob.created_at.asc())
            .limit(sample_limit)
        ).scalars().all()
    )

    action_count_rows = db.execute(
        select(AuditLog.action, func.count())
        .where(
            AuditLog.target_type == "contract_job",
            AuditLog.created_at >= window_start,
        )
        .group_by(AuditLog.action)
        .order_by(func.count().desc(), AuditLog.action.asc())
    ).all()
    action_counts = [
        ContractJobOpsActionCount(action=str(action), count=int(count))
        for action, count in action_count_rows
    ]

    recent_rows = db.execute(
        select(AuditLog)
        .where(
            AuditLog.target_type == "contract_job",
            AuditLog.created_at >= window_start,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(events_limit)
    ).scalars().all()
    recent_events = [
        ContractJobOpsEventEntry(
            created_at=row.created_at,
            actor_type=row.actor_type.value,
            actor_id=row.actor_id,
            action=row.action,
            target_id=row.target_id,
            details=row.details,
        )
        for row in recent_rows
    ]

    return ContractJobOpsOverviewOut(
        generated_at=now,
        summary=summary,
        action_counts=action_counts,
        recent_events=recent_events,
        samples=ContractJobOpsSamples(
            stale_processing=[ContractJobOpsSampleItem.model_validate(item) for item in stale_processing],
            failed_retryable=[ContractJobOpsSampleItem.model_validate(item) for item in failed_retryable],
            new_exhausted=[ContractJobOpsSampleItem.model_validate(item) for item in new_exhausted],
        ),
        window_hours=window_hours,
        stale_minutes=stale_minutes,
        sample_limit=sample_limit,
        events_limit=events_limit,
    )


@router.post("/maintenance", response_model=ContractJobMaintenanceOut)
def contract_jobs_maintenance(
    dry_run: bool = Query(default=True),
    stale_minutes: int = Query(default=30, ge=1, le=240),
    limit_each: int = Query(default=200, ge=1, le=1000),
    reset_stale: bool = Query(default=True),
    finalize_exhausted_new: bool = Query(default=True),
    retry_failed: bool = Query(default=False),
    retry_failed_only_retryable: bool = Query(default=True),
    retry_failed_older_than_minutes: int | None = Query(default=None, ge=1, le=10080),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJobMaintenanceOut:
    now = datetime.now(timezone.utc)
    before_summary = _build_contract_job_summary(
        db,
        now=now,
        window_hours=24,
        stale_minutes=stale_minutes,
    )

    reset_rows: list[ContractJob] = []
    finalize_rows: list[ContractJob] = []
    retry_rows: list[ContractJob] = []

    if reset_stale:
        reset_rows = list(
            db.execute(
                select(ContractJob)
                .where(
                    ContractJob.status == ContractJobStatus.processing,
                    ContractJob.updated_at < (now - timedelta(minutes=stale_minutes)),
                )
                .order_by(ContractJob.updated_at.asc(), ContractJob.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(limit_each)
            ).scalars().all()
        )
    if finalize_exhausted_new:
        finalize_rows = list(
            db.execute(
                select(ContractJob)
                .where(
                    ContractJob.status == ContractJobStatus.new,
                    ContractJob.attempts >= ContractJob.max_attempts,
                )
                .order_by(ContractJob.updated_at.asc(), ContractJob.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(limit_each)
            ).scalars().all()
        )
    if retry_failed:
        retry_stmt = (
            select(ContractJob)
            .where(ContractJob.status == ContractJobStatus.failed)
            .order_by(ContractJob.updated_at.asc(), ContractJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit_each)
        )
        if retry_failed_only_retryable:
            retry_stmt = retry_stmt.where(ContractJob.attempts < ContractJob.max_attempts)
        if retry_failed_older_than_minutes is not None:
            retry_stmt = retry_stmt.where(
                ContractJob.updated_at < (now - timedelta(minutes=retry_failed_older_than_minutes))
            )
        retry_rows = list(db.execute(retry_stmt).scalars().all())

    reset_requeued_count = 0
    reset_failed_terminal_count = 0
    applied_reset_count = 0
    applied_finalize_count = 0
    applied_retry_count = 0

    if dry_run:
        db.commit()
    else:
        for job in reset_rows:
            job.attempts = min(job.max_attempts, job.attempts + 1)
            job.worker_id = None
            if job.attempts >= job.max_attempts:
                job.status = ContractJobStatus.failed
                job.last_error = "stale processing reset (max attempts reached)"
                reset_failed_terminal_count += 1
            else:
                job.status = ContractJobStatus.new
                job.last_error = "stale processing reset"
                reset_requeued_count += 1
            job.updated_at = now
            db.add(job)
            write_audit(
                db,
                actor_type=ActorType.api_key,
                actor_id=identity.name,
                action="job.reset_stale",
                target_type="contract_job",
                target_id=job.id,
                details={
                    "older_than_minutes": stale_minutes,
                    "result_status": job.status.value,
                    "source": "maintenance",
                },
            )
            applied_reset_count += 1

        for job in finalize_rows:
            job.status = ContractJobStatus.failed
            if not job.last_error:
                job.last_error = "exhausted attempts finalized from new queue"
            job.updated_at = now
            db.add(job)
            write_audit(
                db,
                actor_type=ActorType.api_key,
                actor_id=identity.name,
                action="job.finalize_exhausted_new",
                target_type="contract_job",
                target_id=job.id,
                details={"source": "maintenance"},
            )
            applied_finalize_count += 1

        for job in retry_rows:
            job.status = ContractJobStatus.new
            job.worker_id = None
            job.last_error = None
            job.updated_at = now
            db.add(job)
            write_audit(
                db,
                actor_type=ActorType.api_key,
                actor_id=identity.name,
                action="job.retry_failed",
                target_type="contract_job",
                target_id=job.id,
                details={
                    "retryable_only": retry_failed_only_retryable,
                    "older_than_minutes": retry_failed_older_than_minutes,
                    "source": "maintenance",
                },
            )
            applied_retry_count += 1
        db.commit()

    after_now = datetime.now(timezone.utc)
    after_summary = _build_contract_job_summary(
        db,
        now=after_now,
        window_hours=24,
        stale_minutes=stale_minutes,
    )
    if dry_run:
        reset_requeued_count = sum(1 for job in reset_rows if (job.attempts + 1) < job.max_attempts)
        reset_failed_terminal_count = len(reset_rows) - reset_requeued_count

    return ContractJobMaintenanceOut(
        generated_at=after_now,
        dry_run=dry_run,
        stale_minutes=stale_minutes,
        before_summary=before_summary,
        after_summary=after_summary,
        reset_stale=ContractJobMaintenanceActionOut(
            requested=reset_stale,
            matched_count=len(reset_rows),
            applied_count=applied_reset_count,
            requeued_count=reset_requeued_count,
            failed_terminal_count=reset_failed_terminal_count,
            job_ids=[job.id for job in reset_rows],
        ),
        finalize_exhausted_new=ContractJobMaintenanceActionOut(
            requested=finalize_exhausted_new,
            matched_count=len(finalize_rows),
            applied_count=applied_finalize_count,
            job_ids=[job.id for job in finalize_rows],
        ),
        retry_failed=ContractJobMaintenanceActionOut(
            requested=retry_failed,
            matched_count=len(retry_rows),
            applied_count=applied_retry_count,
            job_ids=[job.id for job in retry_rows],
        ),
    )


@router.post("/{job_id}/requeue", response_model=ContractJobOut)
def requeue_contract_job(
    job_id: uuid.UUID,
    force: bool = Query(default=False),
    increment_attempt: bool = Query(default=True),
    reason: str | None = Query(default=None, min_length=1, max_length=500),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJob:
    job = db.get(ContractJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    prev_status = job.status
    if not force:
        if prev_status == ContractJobStatus.done:
            raise HTTPException(status_code=409, detail="Done job cannot be requeued without force")
        if prev_status == ContractJobStatus.failed and job.attempts >= job.max_attempts:
            raise HTTPException(status_code=409, detail="Terminal failed job requires force=true")
        if prev_status == ContractJobStatus.processing and job.attempts >= job.max_attempts:
            raise HTTPException(status_code=409, detail="Processing job exhausted max_attempts; use force=true")

    if increment_attempt and prev_status == ContractJobStatus.processing and job.attempts < job.max_attempts:
        job.attempts += 1

    job.status = ContractJobStatus.new
    job.worker_id = None
    job.last_error = reason or None
    job.updated_at = datetime.now(timezone.utc)
    db.add(job)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="job.requeue",
        target_type="contract_job",
        target_id=job.id,
        details={
            "previous_status": prev_status.value,
            "force": force,
            "increment_attempt": increment_attempt,
            "reason": reason,
        },
    )
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/touch", response_model=ContractJobOut)
def touch_contract_job(
    job_id: uuid.UUID,
    payload: ContractJobTouch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJob:
    job = db.get(ContractJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != ContractJobStatus.processing:
        raise HTTPException(status_code=409, detail="Only processing jobs can be touched")
    if payload.worker_id and job.worker_id and payload.worker_id != job.worker_id:
        raise HTTPException(status_code=409, detail="worker_id does not match claimed worker")

    job.updated_at = datetime.now(timezone.utc)
    db.add(job)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="job.touch",
        target_type="contract_job",
        target_id=job.id,
        details=payload.model_dump(exclude_none=True),
    )
    db.commit()
    db.refresh(job)
    return job


@router.post("/retry-failed", response_model=ContractJobBulkRetryOut)
def retry_failed_contract_jobs(
    limit: int = Query(default=100, ge=1, le=500),
    retryable_only: bool = Query(default=True),
    older_than_minutes: int | None = Query(default=None, ge=1, le=10080),
    dry_run: bool = Query(default=False),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJobBulkRetryOut:
    now = datetime.now(timezone.utc)
    stmt = (
        select(ContractJob)
        .where(ContractJob.status == ContractJobStatus.failed)
        .order_by(ContractJob.updated_at.asc(), ContractJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
    )
    if retryable_only:
        stmt = stmt.where(ContractJob.attempts < ContractJob.max_attempts)
    if older_than_minutes is not None:
        stmt = stmt.where(ContractJob.updated_at < (now - timedelta(minutes=older_than_minutes)))

    rows = list(db.execute(stmt).scalars().all())
    job_ids = [row.id for row in rows]
    if dry_run:
        db.commit()
        return ContractJobBulkRetryOut(
            requested_limit=limit,
            matched_count=len(rows),
            retried_count=0,
            retryable_only=retryable_only,
            dry_run=True,
            older_than_minutes=older_than_minutes,
            job_ids=job_ids,
        )

    for job in rows:
        job.status = ContractJobStatus.new
        job.worker_id = None
        job.last_error = None
        job.updated_at = now
        db.add(job)
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="job.retry_failed",
            target_type="contract_job",
            target_id=job.id,
            details={
                "retryable_only": retryable_only,
                "older_than_minutes": older_than_minutes,
            },
        )

    db.commit()
    return ContractJobBulkRetryOut(
        requested_limit=limit,
        matched_count=len(rows),
        retried_count=len(rows),
        retryable_only=retryable_only,
        dry_run=False,
        older_than_minutes=older_than_minutes,
        job_ids=job_ids,
    )


@router.post("/finalize-exhausted-new", response_model=ContractJobFinalizeExhaustedOut)
def finalize_exhausted_new_jobs(
    limit: int = Query(default=200, ge=1, le=1000),
    dry_run: bool = Query(default=False),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJobFinalizeExhaustedOut:
    now = datetime.now(timezone.utc)
    rows = list(
        db.execute(
            select(ContractJob)
            .where(
                ContractJob.status == ContractJobStatus.new,
                ContractJob.attempts >= ContractJob.max_attempts,
            )
            .order_by(ContractJob.updated_at.asc(), ContractJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        ).scalars().all()
    )
    job_ids = [row.id for row in rows]
    if dry_run:
        db.commit()
        return ContractJobFinalizeExhaustedOut(
            requested_limit=limit,
            matched_count=len(rows),
            finalized_count=0,
            dry_run=True,
            job_ids=job_ids,
        )

    for job in rows:
        job.status = ContractJobStatus.failed
        if not job.last_error:
            job.last_error = "exhausted attempts finalized from new queue"
        job.updated_at = now
        db.add(job)
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="job.finalize_exhausted_new",
            target_type="contract_job",
            target_id=job.id,
        )

    db.commit()
    return ContractJobFinalizeExhaustedOut(
        requested_limit=limit,
        matched_count=len(rows),
        finalized_count=len(rows),
        dry_run=False,
        job_ids=job_ids,
    )


@router.get("/{job_id}", response_model=ContractJobOut)
def get_contract_job(
    job_id: uuid.UUID,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.bot, Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJob:
    _ = identity
    job = db.get(ContractJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/history", response_model=ContractJobHistoryResponse)
def get_contract_job_history(
    job_id: uuid.UUID,
    limit: int = Query(default=30, ge=1, le=200),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJobHistoryResponse:
    _ = identity
    job = db.get(ContractJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    rows = db.execute(
        select(AuditLog)
        .where(
            AuditLog.target_type == "contract_job",
            AuditLog.target_id == job_id,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).scalars().all()
    entries = [
        ContractJobHistoryEntry(
            created_at=row.created_at,
            actor_type=row.actor_type.value,
            actor_id=row.actor_id,
            action=row.action,
            details=row.details,
        )
        for row in rows
    ]
    return ContractJobHistoryResponse(job_id=job_id, entries=entries)


@router.post("/claim", response_model=ContractJobOut)
def claim_contract_job(
    payload: ClaimRequest,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJob | Response:
    worker_id = payload.worker_id or socket.gethostname()
    stmt = (
        select(ContractJob)
        .where(
            ContractJob.status == ContractJobStatus.new,
            ContractJob.attempts < ContractJob.max_attempts,
        )
        .order_by(ContractJob.priority.asc(), ContractJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        db.commit()
        return Response(status_code=204)

    job.status = ContractJobStatus.processing
    job.worker_id = worker_id
    job.updated_at = datetime.now(timezone.utc)
    db.add(job)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="job.claim",
        target_type="contract_job",
        target_id=job.id,
        details={"worker_id": worker_id},
    )
    db.commit()
    db.refresh(job)
    return job


@router.patch("/{job_id}", response_model=ContractJobOut)
def patch_contract_job(
    job_id: uuid.UUID,
    payload: ContractJobPatch,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJob:
    job = db.get(ContractJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(job, field, value)

    if payload.status == ContractJobStatus.failed:
        job.attempts += 1
    job.updated_at = datetime.now(timezone.utc)

    db.add(job)
    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="job.update",
        target_type="contract_job",
        target_id=job.id,
        details=changes,
    )
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/result", response_model=ContractJobOut)
def submit_contract_job_result(
    job_id: uuid.UUID,
    payload: ContractJobResult,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJob:
    job = db.get(ContractJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    job.result_summary = payload.result_summary
    job.result_json = payload.result_json
    job.report_url = payload.report_url
    job.status = ContractJobStatus.done
    job.updated_at = datetime.now(timezone.utc)
    db.add(job)

    write_audit(
        db,
        actor_type=ActorType.api_key,
        actor_id=identity.name,
        action="job.result",
        target_type="contract_job",
        target_id=job.id,
    )
    db.commit()
    db.refresh(job)
    return job


@router.post("/reset-stale", response_model=dict[str, int])
def reset_stale_jobs(
    older_than_minutes: int = Query(default=30, ge=1, le=240),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.admin)),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    _ = identity
    threshold = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    now = datetime.now(timezone.utc)
    stale_rows = db.execute(
        select(ContractJob).where(
            ContractJob.status == ContractJobStatus.processing,
            ContractJob.updated_at < threshold,
        )
    ).scalars().all()

    reset_count = 0
    requeued_count = 0
    failed_terminal_count = 0
    for job in stale_rows:
        job.attempts = min(job.max_attempts, job.attempts + 1)
        job.worker_id = None
        if job.attempts >= job.max_attempts:
            job.status = ContractJobStatus.failed
            job.last_error = "stale processing reset (max attempts reached)"
            failed_terminal_count += 1
        else:
            job.status = ContractJobStatus.new
            job.last_error = "stale processing reset"
            requeued_count += 1
        job.updated_at = now
        db.add(job)
        write_audit(
            db,
            actor_type=ActorType.api_key,
            actor_id=identity.name,
            action="job.reset_stale",
            target_type="contract_job",
            target_id=job.id,
            details={
                "older_than_minutes": older_than_minutes,
                "result_status": job.status.value,
            },
        )
        reset_count += 1

    db.commit()
    return {
        "reset_count": reset_count,
        "requeued_count": requeued_count,
        "failed_terminal_count": failed_terminal_count,
    }
