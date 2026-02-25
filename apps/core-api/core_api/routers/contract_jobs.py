from __future__ import annotations

import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core_api.audit import write_audit
from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.db import get_db
from core_api.models import ActorType, ContractJob, ContractJobStatus, Scope
from core_api.schemas import (
    ClaimRequest,
    ContractJobCreate,
    ContractJobOut,
    ContractJobPatch,
    ContractJobResult,
)

router = APIRouter(prefix="/api/v1/contract-jobs", tags=["contract-jobs"])


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
    limit: int = Query(default=20, ge=1, le=100),
    count_only: bool = Query(default=False),
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> Any:
    _ = identity
    if count_only:
        stmt = select(func.count()).select_from(ContractJob)
        if status:
            stmt = stmt.where(ContractJob.status == status)
        count = db.execute(stmt).scalar_one()
        return {"count": count}

    stmt = select(ContractJob).order_by(ContractJob.priority.asc(), ContractJob.created_at.asc()).limit(limit)
    if status:
        stmt = stmt.where(ContractJob.status == status)
    return list(db.execute(stmt).scalars().all())


@router.post("/claim", response_model=ContractJobOut)
def claim_contract_job(
    payload: ClaimRequest,
    identity: ApiKeyIdentity = Depends(require_scopes(Scope.worker, Scope.admin)),
    db: Session = Depends(get_db),
) -> ContractJob | Response:
    worker_id = payload.worker_id or socket.gethostname()
    stmt = (
        select(ContractJob)
        .where(ContractJob.status == ContractJobStatus.new)
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
    stale_rows = db.execute(
        select(ContractJob).where(
            ContractJob.status == ContractJobStatus.processing,
            ContractJob.updated_at < threshold,
            ContractJob.attempts < ContractJob.max_attempts,
        )
    ).scalars().all()

    reset_count = 0
    for job in stale_rows:
        job.status = ContractJobStatus.new
        job.worker_id = None
        job.attempts += 1
        job.updated_at = datetime.now(timezone.utc)
        db.add(job)
        reset_count += 1

    db.commit()
    return {"reset_count": reset_count}
