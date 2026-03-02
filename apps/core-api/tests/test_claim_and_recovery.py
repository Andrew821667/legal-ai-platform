from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    ContractJob,
    ContractJobStatus,
    InputMode,
    ScheduledPost,
    ScheduledPostStatus,
    Scope,
)
from core_api.security import generate_api_key, hash_api_key


def _create_api_key(scope: Scope, name: str) -> str:
    raw_key = generate_api_key()
    db = SessionLocal()
    try:
        db.add(
            ApiKey(
                key_hash=hash_api_key(raw_key),
                scope=scope,
                name=name,
                is_active=True,
            )
        )
        db.commit()
        cache.invalidate()
    finally:
        db.close()
    return raw_key


def _delete_api_key_by_name(name: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(ApiKey).where(ApiKey.name == name))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def test_claim_scheduled_posts_marks_publishing() -> None:
    client = TestClient(app)
    api_key_name = "pytest.news.claim.scheduled"
    raw_key = _create_api_key(Scope.news, api_key_name)
    created_ids: list = []

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        due_post = ScheduledPost(
            text="due post",
            publish_at=now - timedelta(days=36500),
            status=ScheduledPostStatus.scheduled,
        )
        future_post = ScheduledPost(
            text="future post",
            publish_at=now + timedelta(hours=3),
            status=ScheduledPostStatus.scheduled,
        )
        db.add_all([due_post, future_post])
        db.commit()
        db.refresh(due_post)
        db.refresh(future_post)
        created_ids.extend([due_post.id, future_post.id])
    finally:
        db.close()

    try:
        response = client.post(
            "/api/v1/scheduled-posts/claim?limit=1",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == str(created_ids[0])
        assert payload[0]["status"] == ScheduledPostStatus.publishing.value
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ScheduledPost).where(ScheduledPost.id.in_(created_ids)))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_claim_failed_scheduled_post_after_cooldown() -> None:
    client = TestClient(app)
    api_key_name = "pytest.news.claim.failed"
    raw_key = _create_api_key(Scope.news, api_key_name)
    post_id = None

    db = SessionLocal()
    try:
        stale_failed = ScheduledPost(
            text="failed post",
            publish_at=datetime.now(timezone.utc) - timedelta(days=36500),
            status=ScheduledPostStatus.failed,
            attempts=1,
            max_attempts=3,
            updated_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add(stale_failed)
        db.commit()
        db.refresh(stale_failed)
        post_id = stale_failed.id
    finally:
        db.close()

    try:
        response = client.post(
            "/api/v1/scheduled-posts/claim?limit=1",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == str(post_id)
        assert payload[0]["status"] == ScheduledPostStatus.publishing.value
    finally:
        if post_id is not None:
            db = SessionLocal()
            try:
                db.execute(delete(ScheduledPost).where(ScheduledPost.id == post_id))
                db.commit()
            finally:
                db.close()
        _delete_api_key_by_name(api_key_name)


def test_claim_contract_job_updates_worker_and_status() -> None:
    client = TestClient(app)
    api_key_name = "pytest.worker.claim.contract"
    raw_key = _create_api_key(Scope.worker, api_key_name)
    created_ids: list = []

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        low_priority = ContractJob(
            status=ContractJobStatus.new,
            priority=5,
            input_mode=InputMode.text_only,
            document_text="low",
            created_at=now - timedelta(minutes=2),
        )
        high_priority = ContractJob(
            status=ContractJobStatus.new,
            priority=-1000000,
            input_mode=InputMode.text_only,
            document_text="high",
            created_at=now - timedelta(minutes=1),
        )
        db.add_all([low_priority, high_priority])
        db.commit()
        db.refresh(low_priority)
        db.refresh(high_priority)
        created_ids.extend([low_priority.id, high_priority.id])
    finally:
        db.close()

    try:
        response = client.post(
            "/api/v1/contract-jobs/claim",
            json={"worker_id": "pytest-worker-1"},
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == str(created_ids[1])
        assert payload["status"] == ContractJobStatus.processing.value
        assert payload["worker_id"] == "pytest-worker-1"

        db = SessionLocal()
        try:
            claimed = db.execute(select(ContractJob).where(ContractJob.id == created_ids[1])).scalar_one()
            assert claimed.status == ContractJobStatus.processing
            assert claimed.worker_id == "pytest-worker-1"
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ContractJob).where(ContractJob.id.in_(created_ids)))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_reset_stale_contract_jobs_returns_to_new() -> None:
    client = TestClient(app)
    api_key_name = "pytest.admin.reset.contract"
    raw_key = _create_api_key(Scope.admin, api_key_name)
    stale_id = None

    db = SessionLocal()
    try:
        stale_job = ContractJob(
            status=ContractJobStatus.processing,
            priority=0,
            input_mode=InputMode.text_only,
            document_text="stale",
            worker_id="worker-A",
            attempts=0,
            max_attempts=3,
            updated_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.add(stale_job)
        db.commit()
        db.refresh(stale_job)
        stale_id = stale_job.id
    finally:
        db.close()

    try:
        response = client.post(
            "/api/v1/contract-jobs/reset-stale?older_than_minutes=30",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        assert response.json()["reset_count"] >= 1

        db = SessionLocal()
        try:
            row = db.execute(select(ContractJob).where(ContractJob.id == stale_id)).scalar_one()
            assert row.status == ContractJobStatus.new
            assert row.worker_id is None
            assert row.attempts == 1
        finally:
            db.close()
    finally:
        if stale_id is not None:
            db = SessionLocal()
            try:
                db.execute(delete(ContractJob).where(ContractJob.id == stale_id))
                db.commit()
            finally:
                db.close()
        _delete_api_key_by_name(api_key_name)
