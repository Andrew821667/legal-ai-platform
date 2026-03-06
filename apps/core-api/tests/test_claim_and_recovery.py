from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    ActorType,
    AuditLog,
    ContractJob,
    ContractJobStatus,
    InputMode,
    Lead,
    LeadSource,
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


def test_claim_does_not_pick_failed_scheduled_post() -> None:
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
        assert response.status_code == 204
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


def test_claim_contract_job_skips_new_jobs_with_exhausted_attempts() -> None:
    client = TestClient(app)
    api_key_name = "pytest.worker.claim.contract.exhausted"
    raw_key = _create_api_key(Scope.worker, api_key_name)
    good_id = None
    exhausted_id = None

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        exhausted = ContractJob(
            status=ContractJobStatus.new,
            priority=-1000000,
            attempts=3,
            max_attempts=3,
            input_mode=InputMode.text_only,
            document_text="exhausted",
            created_at=now - timedelta(minutes=3),
        )
        good = ContractJob(
            status=ContractJobStatus.new,
            priority=-999999,
            attempts=0,
            max_attempts=3,
            input_mode=InputMode.text_only,
            document_text="good",
            created_at=now - timedelta(minutes=2),
        )
        db.add_all([exhausted, good])
        db.commit()
        db.refresh(exhausted)
        db.refresh(good)
        exhausted_id = exhausted.id
        good_id = good.id
    finally:
        db.close()

    try:
        response = client.post(
            "/api/v1/contract-jobs/claim",
            json={"worker_id": "pytest-worker-claim-exhausted"},
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == str(good_id)
    finally:
        db = SessionLocal()
        try:
            if exhausted_id is not None:
                db.execute(delete(ContractJob).where(ContractJob.id == exhausted_id))
            if good_id is not None:
                db.execute(delete(ContractJob).where(ContractJob.id == good_id))
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


def test_reset_stale_contract_jobs_moves_to_failed_when_attempts_exhausted() -> None:
    client = TestClient(app)
    api_key_name = "pytest.admin.reset.contract.terminal"
    raw_key = _create_api_key(Scope.admin, api_key_name)
    stale_id = None

    db = SessionLocal()
    try:
        stale_job = ContractJob(
            status=ContractJobStatus.processing,
            priority=0,
            input_mode=InputMode.text_only,
            document_text="stale-terminal",
            worker_id="worker-B",
            attempts=2,
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
        payload = response.json()
        assert payload["reset_count"] >= 1
        assert payload["failed_terminal_count"] >= 1

        db = SessionLocal()
        try:
            row = db.execute(select(ContractJob).where(ContractJob.id == stale_id)).scalar_one()
            assert row.status == ContractJobStatus.failed
            assert row.worker_id is None
            assert row.attempts == 3
            assert row.last_error is not None
        finally:
            db.close()
    finally:
        if stale_id is not None:
            db = SessionLocal()
            try:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.target_type == "contract_job",
                        AuditLog.target_id == stale_id,
                        AuditLog.action == "job.reset_stale",
                    )
                )
                db.execute(delete(ContractJob).where(ContractJob.id == stale_id))
                db.commit()
            finally:
                db.close()
        _delete_api_key_by_name(api_key_name)


def test_contract_jobs_support_get_by_id_and_filters() -> None:
    client = TestClient(app)
    worker_key_name = "pytest.worker.contract.filters"
    bot_key_name = "pytest.bot.contract.get"
    raw_worker_key = _create_api_key(Scope.worker, worker_key_name)
    raw_bot_key = _create_api_key(Scope.bot, bot_key_name)

    lead_a_id = None
    lead_b_id = None
    job_a_id = None
    job_b_id = None

    db = SessionLocal()
    try:
        lead_a = Lead(source=LeadSource.telegram_bot, name="Lead A")
        lead_b = Lead(source=LeadSource.telegram_bot, name="Lead B")
        db.add_all([lead_a, lead_b])
        db.commit()
        db.refresh(lead_a)
        db.refresh(lead_b)
        lead_a_id = lead_a.id
        lead_b_id = lead_b.id

        job_a = ContractJob(
            lead_id=lead_a.id,
            worker_id="worker-a",
            status=ContractJobStatus.processing,
            input_mode=InputMode.text_only,
            document_text="job-a",
        )
        job_b = ContractJob(
            lead_id=lead_b.id,
            worker_id="worker-b",
            status=ContractJobStatus.new,
            input_mode=InputMode.text_only,
            document_text="job-b",
        )
        db.add_all([job_a, job_b])
        db.commit()
        db.refresh(job_a)
        db.refresh(job_b)
        job_a_id = job_a.id
        job_b_id = job_b.id
    finally:
        db.close()

    try:
        by_lead = client.get(
            f"/api/v1/contract-jobs?lead_id={lead_a_id}",
            headers={"X-API-Key": raw_worker_key},
        )
        assert by_lead.status_code == 200
        assert len(by_lead.json()) == 1
        assert by_lead.json()[0]["id"] == str(job_a_id)

        by_worker = client.get(
            "/api/v1/contract-jobs?worker_id=worker-b",
            headers={"X-API-Key": raw_worker_key},
        )
        assert by_worker.status_code == 200
        assert len(by_worker.json()) == 1
        assert by_worker.json()[0]["id"] == str(job_b_id)

        by_id = client.get(
            f"/api/v1/contract-jobs/{job_a_id}",
            headers={"X-API-Key": raw_bot_key},
        )
        assert by_id.status_code == 200
        assert by_id.json()["id"] == str(job_a_id)

        missing = client.get(
            "/api/v1/contract-jobs/11111111-1111-1111-1111-111111111111",
            headers={"X-API-Key": raw_bot_key},
        )
        assert missing.status_code == 404
    finally:
        db = SessionLocal()
        try:
            if job_a_id is not None:
                db.execute(delete(ContractJob).where(ContractJob.id == job_a_id))
            if job_b_id is not None:
                db.execute(delete(ContractJob).where(ContractJob.id == job_b_id))
            if lead_a_id is not None:
                db.execute(delete(Lead).where(Lead.id == lead_a_id))
            if lead_b_id is not None:
                db.execute(delete(Lead).where(Lead.id == lead_b_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(worker_key_name)
        _delete_api_key_by_name(bot_key_name)


def test_contract_jobs_summary_returns_operational_counts() -> None:
    client = TestClient(app)
    api_key_name = "pytest.worker.contract.summary"
    raw_key = _create_api_key(Scope.worker, api_key_name)
    created_ids: list = []

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = [
            ContractJob(
                status=ContractJobStatus.new,
                input_mode=InputMode.text_only,
                document_text="new",
                priority=0,
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
            ),
            ContractJob(
                status=ContractJobStatus.new,
                input_mode=InputMode.text_only,
                document_text="new exhausted",
                attempts=3,
                max_attempts=3,
                priority=0,
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
            ),
            ContractJob(
                status=ContractJobStatus.processing,
                input_mode=InputMode.text_only,
                document_text="processing stale",
                worker_id="worker-summary",
                priority=1,
                created_at=now - timedelta(hours=3),
                updated_at=now - timedelta(hours=2),
            ),
            ContractJob(
                status=ContractJobStatus.failed,
                input_mode=InputMode.text_only,
                document_text="failed retryable",
                attempts=1,
                max_attempts=3,
                priority=2,
                created_at=now - timedelta(hours=1),
                updated_at=now - timedelta(minutes=40),
            ),
            ContractJob(
                status=ContractJobStatus.failed,
                input_mode=InputMode.text_only,
                document_text="failed terminal",
                attempts=3,
                max_attempts=3,
                priority=3,
                created_at=now - timedelta(hours=1),
                updated_at=now - timedelta(minutes=20),
            ),
            ContractJob(
                status=ContractJobStatus.done,
                input_mode=InputMode.text_only,
                document_text="done recent",
                priority=4,
                created_at=now - timedelta(hours=1),
                updated_at=now - timedelta(minutes=10),
            ),
        ]
        db.add_all(rows)
        db.commit()
        for row in rows:
            db.refresh(row)
            created_ids.append(row.id)
    finally:
        db.close()

    try:
        response = client.get(
            "/api/v1/contract-jobs/summary?window_hours=24&stale_minutes=30",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["by_status"]["new"] >= 1
        assert payload["new_retryable_count"] >= 1
        assert payload["new_exhausted_count"] >= 1
        assert payload["by_status"]["processing"] >= 1
        assert payload["by_status"]["failed"] >= 2
        assert payload["by_status"]["done"] >= 1
        assert payload["processing_stale_count"] >= 1
        assert payload["failed_retryable_count"] >= 1
        assert payload["failed_terminal_count"] >= 1
        assert payload["done_last_hours_count"] >= 1
        assert payload["new_oldest_created_at"] is not None
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ContractJob).where(ContractJob.id.in_(created_ids)))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_contract_jobs_ops_overview_returns_samples_and_recent_events() -> None:
    client = TestClient(app)
    api_key_name = "pytest.worker.contract.ops_overview"
    raw_key = _create_api_key(Scope.worker, api_key_name)
    created_ids: list = []
    audit_id = None

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = [
            ContractJob(
                status=ContractJobStatus.processing,
                input_mode=InputMode.text_only,
                document_text="processing stale",
                worker_id="worker-ops",
                attempts=0,
                max_attempts=3,
                created_at=now - timedelta(hours=3),
                updated_at=now - timedelta(hours=2),
            ),
            ContractJob(
                status=ContractJobStatus.failed,
                input_mode=InputMode.text_only,
                document_text="failed retryable",
                attempts=1,
                max_attempts=3,
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=1),
            ),
            ContractJob(
                status=ContractJobStatus.new,
                input_mode=InputMode.text_only,
                document_text="new exhausted",
                attempts=3,
                max_attempts=3,
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=1),
            ),
        ]
        db.add_all(rows)
        db.commit()
        for row in rows:
            db.refresh(row)
            created_ids.append(row.id)

        audit = AuditLog(
            actor_type=ActorType.api_key,
            actor_id="pytest.ops",
            action="job.ops.test",
            target_type="contract_job",
            target_id=rows[0].id,
            details={"source": "test"},
            created_at=now - timedelta(minutes=5),
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        audit_id = audit.id
    finally:
        db.close()

    try:
        response = client.get(
            "/api/v1/contract-jobs/ops-overview?window_hours=24&stale_minutes=30&sample_limit=10&events_limit=20",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["processing_stale_count"] >= 1
        assert payload["summary"]["failed_retryable_count"] >= 1
        assert payload["summary"]["new_exhausted_count"] >= 1
        assert len(payload["samples"]["stale_processing"]) >= 1
        assert len(payload["samples"]["failed_retryable"]) >= 1
        assert len(payload["samples"]["new_exhausted"]) >= 1

        actions = [entry["action"] for entry in payload["recent_events"]]
        assert "job.ops.test" in actions
        action_counts = {entry["action"]: entry["count"] for entry in payload["action_counts"]}
        assert action_counts.get("job.ops.test", 0) >= 1
    finally:
        db = SessionLocal()
        try:
            if audit_id is not None:
                db.execute(delete(AuditLog).where(AuditLog.id == audit_id))
            if created_ids:
                db.execute(delete(ContractJob).where(ContractJob.id.in_(created_ids)))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_contract_job_history_returns_audit_entries() -> None:
    client = TestClient(app)
    api_key_name = "pytest.worker.contract.history"
    raw_key = _create_api_key(Scope.worker, api_key_name)
    job_id = None

    db = SessionLocal()
    try:
        job = ContractJob(
            status=ContractJobStatus.new,
            input_mode=InputMode.text_only,
            document_text="history",
            priority=-1000000000,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    try:
        claim = client.post(
            "/api/v1/contract-jobs/claim",
            json={"worker_id": "worker-history"},
            headers={"X-API-Key": raw_key},
        )
        assert claim.status_code == 200
        assert claim.json()["id"] == str(job_id)

        patch = client.patch(
            f"/api/v1/contract-jobs/{job_id}",
            json={"status": "failed", "last_error": "network"},
            headers={"X-API-Key": raw_key},
        )
        assert patch.status_code == 200

        history = client.get(
            f"/api/v1/contract-jobs/{job_id}/history?limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert history.status_code == 200
        payload = history.json()
        assert payload["job_id"] == str(job_id)
        actions = [entry["action"] for entry in payload["entries"]]
        assert "job.claim" in actions
        assert "job.update" in actions
    finally:
        db = SessionLocal()
        try:
            if job_id is not None:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.target_type == "contract_job",
                        AuditLog.target_id == job_id,
                    )
                )
                db.execute(delete(ContractJob).where(ContractJob.id == job_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_contract_jobs_pagination_sort_and_sla_filters() -> None:
    client = TestClient(app)
    api_key_name = "pytest.worker.contract.sla"
    raw_key = _create_api_key(Scope.worker, api_key_name)
    created_ids: list = []

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = [
            ContractJob(
                status=ContractJobStatus.new,
                input_mode=InputMode.text_only,
                document_text="new old",
                priority=10,
                created_at=now - timedelta(hours=3),
                updated_at=now - timedelta(hours=3),
            ),
            ContractJob(
                status=ContractJobStatus.new,
                input_mode=InputMode.text_only,
                document_text="new fresh",
                priority=1,
                created_at=now - timedelta(minutes=20),
                updated_at=now - timedelta(minutes=20),
            ),
            ContractJob(
                status=ContractJobStatus.processing,
                input_mode=InputMode.text_only,
                document_text="processing stale",
                worker_id="w1",
                priority=2,
                created_at=now - timedelta(hours=4),
                updated_at=now - timedelta(hours=2),
            ),
            ContractJob(
                status=ContractJobStatus.processing,
                input_mode=InputMode.text_only,
                document_text="processing fresh",
                worker_id="w2",
                priority=3,
                created_at=now - timedelta(hours=1),
                updated_at=now - timedelta(minutes=5),
            ),
            ContractJob(
                status=ContractJobStatus.failed,
                input_mode=InputMode.text_only,
                document_text="failed retryable",
                attempts=1,
                max_attempts=3,
                priority=4,
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=1),
            ),
            ContractJob(
                status=ContractJobStatus.failed,
                input_mode=InputMode.text_only,
                document_text="failed terminal",
                attempts=3,
                max_attempts=3,
                priority=5,
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=1),
            ),
        ]
        db.add_all(rows)
        db.commit()
        for row in rows:
            db.refresh(row)
            created_ids.append(row.id)
    finally:
        db.close()

    try:
        stale_processing = client.get(
            "/api/v1/contract-jobs?stale_processing_only=true&stale_minutes=30&limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert stale_processing.status_code == 200
        stale_payload = stale_processing.json()
        assert all(item["status"] == ContractJobStatus.processing.value for item in stale_payload)
        assert any(item["worker_id"] == "w1" for item in stale_payload)
        assert all(item["worker_id"] != "w2" for item in stale_payload)

        retryable_failed = client.get(
            "/api/v1/contract-jobs?failed_retryable_only=true&limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert retryable_failed.status_code == 200
        retry_payload = retryable_failed.json()
        assert len(retry_payload) >= 1
        assert all(item["status"] == ContractJobStatus.failed.value for item in retry_payload)
        assert all(item["attempts"] < item["max_attempts"] for item in retry_payload)

        old_new = client.get(
            "/api/v1/contract-jobs?new_older_than_minutes=60&limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert old_new.status_code == 200
        old_new_payload = old_new.json()
        assert len(old_new_payload) >= 1
        assert all(item["status"] == ContractJobStatus.new.value for item in old_new_payload)

        paged = client.get(
            "/api/v1/contract-jobs?order_by=created_at&order_dir=desc&limit=2&offset=1",
            headers={"X-API-Key": raw_key},
        )
        assert paged.status_code == 200
        paged_payload = paged.json()
        assert len(paged_payload) == 2
        first_created = datetime.fromisoformat(paged_payload[0]["created_at"])
        second_created = datetime.fromisoformat(paged_payload[1]["created_at"])
        assert first_created >= second_created

        count_old_new = client.get(
            "/api/v1/contract-jobs?count_only=true&new_older_than_minutes=60",
            headers={"X-API-Key": raw_key},
        )
        assert count_old_new.status_code == 200
        assert count_old_new.json()["count"] >= 1
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ContractJob).where(ContractJob.id.in_(created_ids)))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_retry_failed_contract_jobs_supports_dry_run_and_applies_retryable_only() -> None:
    client = TestClient(app)
    api_key_name = "pytest.admin.contract.retry_failed"
    raw_key = _create_api_key(Scope.admin, api_key_name)
    retryable_id = None
    terminal_id = None

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        retryable = ContractJob(
            status=ContractJobStatus.failed,
            input_mode=InputMode.text_only,
            document_text="retryable",
            attempts=1,
            max_attempts=3,
            worker_id="worker-r",
            last_error="temporary",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
        terminal = ContractJob(
            status=ContractJobStatus.failed,
            input_mode=InputMode.text_only,
            document_text="terminal",
            attempts=3,
            max_attempts=3,
            worker_id="worker-t",
            last_error="terminal",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
        db.add_all([retryable, terminal])
        db.commit()
        db.refresh(retryable)
        db.refresh(terminal)
        retryable_id = retryable.id
        terminal_id = terminal.id
    finally:
        db.close()

    try:
        dry = client.post(
            "/api/v1/contract-jobs/retry-failed?limit=10&dry_run=true",
            headers={"X-API-Key": raw_key},
        )
        assert dry.status_code == 200
        dry_payload = dry.json()
        assert dry_payload["dry_run"] is True
        assert dry_payload["matched_count"] >= 1
        assert dry_payload["retried_count"] == 0

        db = SessionLocal()
        try:
            still_failed = db.execute(select(ContractJob).where(ContractJob.id == retryable_id)).scalar_one()
            assert still_failed.status == ContractJobStatus.failed
        finally:
            db.close()

        do_retry = client.post(
            "/api/v1/contract-jobs/retry-failed?limit=10&retryable_only=true",
            headers={"X-API-Key": raw_key},
        )
        assert do_retry.status_code == 200
        payload = do_retry.json()
        assert payload["dry_run"] is False
        assert payload["retried_count"] >= 1
        assert str(retryable_id) in payload["job_ids"]
        assert str(terminal_id) not in payload["job_ids"]

        db = SessionLocal()
        try:
            retryable_row = db.execute(select(ContractJob).where(ContractJob.id == retryable_id)).scalar_one()
            terminal_row = db.execute(select(ContractJob).where(ContractJob.id == terminal_id)).scalar_one()
            assert retryable_row.status == ContractJobStatus.new
            assert retryable_row.worker_id is None
            assert retryable_row.last_error is None
            assert terminal_row.status == ContractJobStatus.failed

            retry_audits = db.execute(
                select(AuditLog).where(
                    AuditLog.target_type == "contract_job",
                    AuditLog.target_id == retryable_id,
                    AuditLog.action == "job.retry_failed",
                )
            ).scalars().all()
            assert len(retry_audits) >= 1
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            if retryable_id is not None:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.target_type == "contract_job",
                        AuditLog.target_id == retryable_id,
                    )
                )
                db.execute(delete(ContractJob).where(ContractJob.id == retryable_id))
            if terminal_id is not None:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.target_type == "contract_job",
                        AuditLog.target_id == terminal_id,
                    )
                )
                db.execute(delete(ContractJob).where(ContractJob.id == terminal_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_requeue_contract_job_requires_force_for_terminal_failed() -> None:
    client = TestClient(app)
    api_key_name = "pytest.admin.contract.requeue"
    raw_key = _create_api_key(Scope.admin, api_key_name)
    terminal_id = None
    processing_id = None

    db = SessionLocal()
    try:
        terminal = ContractJob(
            status=ContractJobStatus.failed,
            input_mode=InputMode.text_only,
            document_text="terminal",
            attempts=3,
            max_attempts=3,
            worker_id="w-terminal",
            last_error="terminal",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            updated_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        processing = ContractJob(
            status=ContractJobStatus.processing,
            input_mode=InputMode.text_only,
            document_text="processing",
            attempts=0,
            max_attempts=3,
            worker_id="w-processing",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            updated_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add_all([terminal, processing])
        db.commit()
        db.refresh(terminal)
        db.refresh(processing)
        terminal_id = terminal.id
        processing_id = processing.id
    finally:
        db.close()

    try:
        no_force = client.post(
            f"/api/v1/contract-jobs/{terminal_id}/requeue",
            headers={"X-API-Key": raw_key},
        )
        assert no_force.status_code == 409

        forced = client.post(
            f"/api/v1/contract-jobs/{terminal_id}/requeue?force=true",
            headers={"X-API-Key": raw_key},
        )
        assert forced.status_code == 200
        assert forced.json()["status"] == ContractJobStatus.new.value

        requeue_processing = client.post(
            f"/api/v1/contract-jobs/{processing_id}/requeue?reason=manual_requeue",
            headers={"X-API-Key": raw_key},
        )
        assert requeue_processing.status_code == 200
        payload = requeue_processing.json()
        assert payload["status"] == ContractJobStatus.new.value
        assert payload["worker_id"] is None
        assert payload["attempts"] == 1
        assert payload["last_error"] == "manual_requeue"

        db = SessionLocal()
        try:
            terminal_row = db.execute(select(ContractJob).where(ContractJob.id == terminal_id)).scalar_one()
            processing_row = db.execute(select(ContractJob).where(ContractJob.id == processing_id)).scalar_one()
            assert terminal_row.status == ContractJobStatus.new
            assert processing_row.status == ContractJobStatus.new

            terminal_audit = db.execute(
                select(AuditLog).where(
                    AuditLog.target_type == "contract_job",
                    AuditLog.target_id == terminal_id,
                    AuditLog.action == "job.requeue",
                )
            ).scalars().all()
            assert len(terminal_audit) >= 1
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            if terminal_id is not None:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.target_type == "contract_job",
                        AuditLog.target_id == terminal_id,
                    )
                )
                db.execute(delete(ContractJob).where(ContractJob.id == terminal_id))
            if processing_id is not None:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.target_type == "contract_job",
                        AuditLog.target_id == processing_id,
                    )
                )
                db.execute(delete(ContractJob).where(ContractJob.id == processing_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_finalize_exhausted_new_jobs_supports_dry_run_and_finalize() -> None:
    client = TestClient(app)
    api_key_name = "pytest.admin.contract.finalize_exhausted"
    raw_key = _create_api_key(Scope.admin, api_key_name)
    exhausted_id = None
    retryable_id = None

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        exhausted = ContractJob(
            status=ContractJobStatus.new,
            input_mode=InputMode.text_only,
            document_text="exhausted new",
            attempts=3,
            max_attempts=3,
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
        retryable = ContractJob(
            status=ContractJobStatus.new,
            input_mode=InputMode.text_only,
            document_text="retryable new",
            attempts=1,
            max_attempts=3,
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
        )
        db.add_all([exhausted, retryable])
        db.commit()
        db.refresh(exhausted)
        db.refresh(retryable)
        exhausted_id = exhausted.id
        retryable_id = retryable.id
    finally:
        db.close()

    try:
        dry = client.post(
            "/api/v1/contract-jobs/finalize-exhausted-new?dry_run=true&limit=50",
            headers={"X-API-Key": raw_key},
        )
        assert dry.status_code == 200
        dry_payload = dry.json()
        assert dry_payload["matched_count"] >= 1
        assert dry_payload["finalized_count"] == 0
        assert str(exhausted_id) in dry_payload["job_ids"]

        db = SessionLocal()
        try:
            exhausted_row = db.execute(select(ContractJob).where(ContractJob.id == exhausted_id)).scalar_one()
            assert exhausted_row.status == ContractJobStatus.new
        finally:
            db.close()

        finalize = client.post(
            "/api/v1/contract-jobs/finalize-exhausted-new?limit=50",
            headers={"X-API-Key": raw_key},
        )
        assert finalize.status_code == 200
        payload = finalize.json()
        assert payload["finalized_count"] >= 1
        assert str(exhausted_id) in payload["job_ids"]
        assert str(retryable_id) not in payload["job_ids"]

        db = SessionLocal()
        try:
            exhausted_row = db.execute(select(ContractJob).where(ContractJob.id == exhausted_id)).scalar_one()
            retryable_row = db.execute(select(ContractJob).where(ContractJob.id == retryable_id)).scalar_one()
            assert exhausted_row.status == ContractJobStatus.failed
            assert retryable_row.status == ContractJobStatus.new
            audits = db.execute(
                select(AuditLog).where(
                    AuditLog.target_type == "contract_job",
                    AuditLog.target_id == exhausted_id,
                    AuditLog.action == "job.finalize_exhausted_new",
                )
            ).scalars().all()
            assert len(audits) >= 1
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            if exhausted_id is not None:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.target_type == "contract_job",
                        AuditLog.target_id == exhausted_id,
                    )
                )
                db.execute(delete(ContractJob).where(ContractJob.id == exhausted_id))
            if retryable_id is not None:
                db.execute(delete(ContractJob).where(ContractJob.id == retryable_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)
