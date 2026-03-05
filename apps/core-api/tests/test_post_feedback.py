from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    Lead,
    LeadStatus,
    LeadSource,
    PostFeedbackSignal,
    PostFeedbackSource,
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


def test_lookup_post_by_telegram_message_and_feedback_snapshot() -> None:
    client = TestClient(app)
    api_key_name = "pytest.news.feedback"
    raw_key = _create_api_key(Scope.news, api_key_name)
    post_id = None

    db = SessionLocal()
    try:
        post = ScheduledPost(
            text="posted post",
            title="Пост с сигналами",
            publish_at=datetime.now(timezone.utc) - timedelta(hours=1),
            status=ScheduledPostStatus.posted,
            telegram_message_id=777,
            channel_username="@legal_ai_pro",
            posted_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        post_id = post.id
    finally:
        db.close()

    try:
        lookup = client.get(
            "/api/v1/scheduled-posts/lookup/by-telegram-message?message_id=777&channel_username=%40legal_ai_pro",
            headers={"X-API-Key": raw_key},
        )
        assert lookup.status_code == 200
        assert lookup.json()["id"] == str(post_id)

        comment_feedback = client.post(
            f"/api/v1/scheduled-posts/{post_id}/feedback",
            json={
                "source": "comment",
                "signal_key": "negative",
                "signal_value": -1,
                "text": "Слишком общо и много воды",
                "telegram_chat_id": "-100123",
                "telegram_message_id": 88001,
                "payload": {"sentiment": "negative", "excerpt": "Слишком общо и много воды"},
            },
            headers={"X-API-Key": raw_key},
        )
        assert comment_feedback.status_code == 200

        reaction_feedback = client.post(
            f"/api/v1/scheduled-posts/{post_id}/feedback",
            json={
                "source": "reaction_count",
                "signal_key": "reaction_count",
                "signal_value": 0,
                "telegram_chat_id": "@legal_ai_pro",
                "telegram_message_id": 777,
                "payload": {
                    "total_count": 7,
                    "positive_count": 5,
                    "negative_count": 2,
                    "top_reactions": [{"reaction": "🔥", "count": 4}],
                },
            },
            headers={"X-API-Key": raw_key},
        )
        assert reaction_feedback.status_code == 200

        post_response = client.get(
            f"/api/v1/scheduled-posts/{post_id}",
            headers={"X-API-Key": raw_key},
        )
        assert post_response.status_code == 200
        snapshot = post_response.json()["feedback_snapshot"]
        assert snapshot["comments_negative"] == 1
        assert snapshot["reaction_positive"] == 5
        assert snapshot["reaction_negative"] == 2
        assert snapshot["reaction_total"] == 7
        assert snapshot["recent_negative_comments"]
        assert snapshot["score"] < 0

        list_feedback = client.get(
            f"/api/v1/scheduled-posts/{post_id}/feedback?limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert list_feedback.status_code == 200
        assert len(list_feedback.json()) == 2
    finally:
        if post_id is not None:
            db = SessionLocal()
            try:
                db.execute(delete(PostFeedbackSignal).where(PostFeedbackSignal.post_id == post_id))
                db.execute(delete(ScheduledPost).where(ScheduledPost.id == post_id))
                db.commit()
            finally:
                db.close()
        _delete_api_key_by_name(api_key_name)


def test_patch_scheduled_post_accepts_datetime_and_delete_post() -> None:
    client = TestClient(app)
    api_key_name = "pytest.news.patch-delete"
    raw_key = _create_api_key(Scope.news, api_key_name)
    post_id = None

    db = SessionLocal()
    try:
        post = ScheduledPost(
            text="review post",
            title="Пост на проверке",
            publish_at=datetime.now(timezone.utc) + timedelta(hours=2),
            status=ScheduledPostStatus.review,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        post_id = post.id
    finally:
        db.close()

    try:
        patch_response = client.patch(
            f"/api/v1/scheduled-posts/{post_id}",
            json={
                "status": "scheduled",
                "publish_at": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            },
            headers={"X-API-Key": raw_key},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["status"] == "scheduled"

        delete_response = client.delete(
            f"/api/v1/scheduled-posts/{post_id}",
            headers={"X-API-Key": raw_key},
        )
        assert delete_response.status_code == 204

        archived_response = client.get(
            f"/api/v1/scheduled-posts/{post_id}",
            headers={"X-API-Key": raw_key},
        )
        assert archived_response.status_code == 200
        payload = archived_response.json()
        assert payload["status"] == "failed"
        assert payload["last_error"] == "deleted_irrelevant"
        assert payload["attempts"] == payload["max_attempts"]
    finally:
        if post_id is not None:
            db = SessionLocal()
            try:
                db.execute(delete(PostFeedbackSignal).where(PostFeedbackSignal.post_id == post_id))
                db.execute(delete(ScheduledPost).where(ScheduledPost.id == post_id))
                db.commit()
            finally:
                db.close()
        _delete_api_key_by_name(api_key_name)


def test_reader_feedback_summary_endpoint() -> None:
    client = TestClient(app)
    api_key_name = "pytest.news.reader-summary"
    raw_key = _create_api_key(Scope.news, api_key_name)
    post_ids: list = []

    db = SessionLocal()
    try:
        post_a = ScheduledPost(
            text="posted post a",
            title="Пост А",
            publish_at=datetime.now(timezone.utc) - timedelta(hours=2),
            status=ScheduledPostStatus.posted,
        )
        post_b = ScheduledPost(
            text="posted post b",
            title="Пост Б",
            publish_at=datetime.now(timezone.utc) - timedelta(hours=1),
            status=ScheduledPostStatus.posted,
        )
        db.add(post_a)
        db.add(post_b)
        db.commit()
        db.refresh(post_a)
        db.refresh(post_b)
        post_ids = [post_a.id, post_b.id]

        db.add_all(
            [
                PostFeedbackSignal(
                    post_id=post_a.id,
                    source=PostFeedbackSource.comment,
                    signal_key="reader.weekly.opened",
                    signal_value=1,
                    actor_name="reader_bot",
                ),
                PostFeedbackSignal(
                    post_id=post_a.id,
                    source=PostFeedbackSource.comment,
                    signal_key="reader.consultation.intent",
                    signal_value=1,
                    actor_name="reader_bot",
                ),
                PostFeedbackSignal(
                    post_id=post_a.id,
                    source=PostFeedbackSource.comment,
                    signal_key="reader.not_useful.too_generic",
                    signal_value=-1,
                    actor_name="reader_bot",
                ),
                PostFeedbackSignal(
                    post_id=post_b.id,
                    source=PostFeedbackSource.comment,
                    signal_key="reader.idea.requested",
                    signal_value=1,
                    actor_name="reader_bot",
                ),
                PostFeedbackSignal(
                    post_id=post_b.id,
                    source=PostFeedbackSource.comment,
                    signal_key="reader.useful",
                    signal_value=1,
                    actor_name="reader_bot",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    try:
        response = client.get(
            "/api/v1/scheduled-posts/feedback/reader-summary?days=7",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        payload = response.json()
        stats = payload["stats"]
        assert stats["signals_total"] >= 5
        assert stats["weekly_opened"] >= 1
        assert stats["consultation_intent"] >= 1
        assert stats["idea_requested"] >= 1
        assert stats["useful_feedback"] >= 1
        assert stats["not_useful_feedback"] >= 1
        assert any(item["reason"] == "too_generic" for item in payload["top_negative_reasons"])
        assert any(item["title"] in {"Пост А", "Пост Б"} for item in payload["top_posts"])
    finally:
        if post_ids:
            db = SessionLocal()
            try:
                db.execute(delete(PostFeedbackSignal).where(PostFeedbackSignal.post_id.in_(post_ids)))
                db.execute(delete(ScheduledPost).where(ScheduledPost.id.in_(post_ids)))
                db.commit()
            finally:
                db.close()
        _delete_api_key_by_name(api_key_name)


def test_reader_funnel_summary_endpoint() -> None:
    client = TestClient(app)
    api_key_name = "pytest.news.reader-funnel"
    raw_key = _create_api_key(Scope.news, api_key_name)
    post_ids: list = []
    lead_ids: list = []

    db = SessionLocal()
    try:
        post = ScheduledPost(
            text="posted post for funnel",
            title="Пост воронки",
            publish_at=datetime.now(timezone.utc) - timedelta(hours=1),
            status=ScheduledPostStatus.posted,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        post_ids = [post.id]

        db.add_all(
            [
                PostFeedbackSignal(
                    post_id=post.id,
                    source=PostFeedbackSource.comment,
                    signal_key="reader.consultation.intent",
                    signal_value=1,
                    actor_name="reader_bot",
                    telegram_user_id=111,
                ),
                PostFeedbackSignal(
                    post_id=post.id,
                    source=PostFeedbackSource.comment,
                    signal_key="reader.idea.requested",
                    signal_value=1,
                    actor_name="reader_bot",
                    telegram_user_id=111,
                ),
            ]
        )

        lead = Lead(
            source=LeadSource.telegram_bot,
            telegram_user_id=111,
            name="Reader Lead",
            email="reader@example.com",
            cta_variant="reader_referral",
            status=LeadStatus.qualified,
            notes="[READER_REFERRAL]\npost_id=...",
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_ids = [lead.id]
    finally:
        db.close()

    try:
        response = client.get(
            "/api/v1/scheduled-posts/feedback/reader-funnel?days=7",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["feedback"]["consultation_users"] >= 1
        assert payload["leads"]["reader_referral_created"] >= 1
        assert payload["conversion"]["consultation_users_to_reader_lead"] >= 1
        assert payload["conversion"]["consultation_to_reader_lead_rate_pct"] >= 0
        assert payload["recent_referrals"]
    finally:
        db = SessionLocal()
        try:
            if post_ids:
                db.execute(delete(PostFeedbackSignal).where(PostFeedbackSignal.post_id.in_(post_ids)))
                db.execute(delete(ScheduledPost).where(ScheduledPost.id.in_(post_ids)))
            if lead_ids:
                db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)
