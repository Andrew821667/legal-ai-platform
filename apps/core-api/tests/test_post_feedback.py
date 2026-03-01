from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, PostFeedbackSignal, ScheduledPost, ScheduledPostStatus, Scope
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
