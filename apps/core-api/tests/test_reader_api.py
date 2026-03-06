from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    Event,
    Lead,
    PostFeedbackSignal,
    ReaderPreference,
    ReaderSavedPost,
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


def test_reader_preferences_feed_and_saved_flow() -> None:
    client = TestClient(app)
    api_key_name = "pytest.reader.feed"
    raw_key = _create_api_key(Scope.news, api_key_name)
    telegram_user_id = 9_880_001
    post_ids: list = []
    ai_post_id = None

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        ai_post = ScheduledPost(
            title="EU AI Act: практический чеклист",
            text="Как юротделу применять AI Act при закупке LLM-решений",
            rubric="ai_law",
            publish_at=now - timedelta(hours=2),
            posted_at=now - timedelta(hours=2),
            status=ScheduledPostStatus.posted,
            feedback_snapshot={"score": -10},
        )
        other_post = ScheduledPost(
            title="Автоматизация CLM: что учесть в договорном контуре",
            text="Разбираем CLM-процессы и контроль SLA",
            rubric="contracts",
            publish_at=now - timedelta(hours=1),
            posted_at=now - timedelta(hours=1),
            status=ScheduledPostStatus.posted,
            feedback_snapshot={"score": 90},
        )
        noise_post = ScheduledPost(
            title="Новости рынка: общее обновление",
            text="Нейтральный пост без приоритета",
            rubric="other",
            publish_at=now - timedelta(minutes=30),
            posted_at=now - timedelta(minutes=30),
            status=ScheduledPostStatus.posted,
            feedback_snapshot={"score": 100},
        )
        db.add_all([ai_post, other_post, noise_post])
        db.commit()
        db.refresh(ai_post)
        db.refresh(other_post)
        db.refresh(noise_post)
        ai_post_id = ai_post.id
        post_ids.extend([ai_post.id, other_post.id, noise_post.id])
    finally:
        db.close()

    try:
        patch_response = client.patch(
            "/api/v1/reader/preferences",
            json={
                "telegram_user_id": telegram_user_id,
                "topics": ["AI_LAW", "ai_law", " ", "contracts"],
                "digest_frequency": "daily",
                "expertise_level": "inhouse",
            },
            headers={"X-API-Key": raw_key},
        )
        assert patch_response.status_code == 200
        preferences = patch_response.json()
        assert preferences["telegram_user_id"] == telegram_user_id
        assert preferences["topics"] == ["ai_law", "contracts"]
        assert preferences["digest_frequency"] == "daily"

        save_response = client.post(
            "/api/v1/reader/save",
            json={
                "telegram_user_id": telegram_user_id,
                "post_id": str(ai_post_id),
                "saved": True,
            },
            headers={"X-API-Key": raw_key},
        )
        assert save_response.status_code == 200
        assert save_response.json() == {"post_id": str(ai_post_id), "saved": True}

        feed_response = client.get(
            f"/api/v1/reader/feed?telegram_user_id={telegram_user_id}&limit=20&days=14",
            headers={"X-API-Key": raw_key},
        )
        assert feed_response.status_code == 200
        feed_items = feed_response.json()
        assert feed_items
        ai_item = next((item for item in feed_items if item["id"] == str(ai_post_id)), None)
        assert ai_item is not None
        assert ai_item["is_saved"] is True

        saved_response = client.get(
            f"/api/v1/reader/saved?telegram_user_id={telegram_user_id}&limit=20",
            headers={"X-API-Key": raw_key},
        )
        assert saved_response.status_code == 200
        assert [item["id"] for item in saved_response.json()] == [str(ai_post_id)]

        unsave_response = client.post(
            "/api/v1/reader/save",
            json={
                "telegram_user_id": telegram_user_id,
                "post_id": str(ai_post_id),
                "saved": False,
            },
            headers={"X-API-Key": raw_key},
        )
        assert unsave_response.status_code == 200
        assert unsave_response.json() == {"post_id": str(ai_post_id), "saved": False}

        saved_after_unsave = client.get(
            f"/api/v1/reader/saved?telegram_user_id={telegram_user_id}&limit=20",
            headers={"X-API-Key": raw_key},
        )
        assert saved_after_unsave.status_code == 200
        assert saved_after_unsave.json() == []
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ReaderSavedPost).where(ReaderSavedPost.telegram_user_id == telegram_user_id))
            db.execute(delete(ReaderPreference).where(ReaderPreference.telegram_user_id == telegram_user_id))
            if post_ids:
                db.execute(delete(PostFeedbackSignal).where(PostFeedbackSignal.post_id.in_(post_ids)))
                db.execute(delete(ScheduledPost).where(ScheduledPost.id.in_(post_ids)))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_reader_feedback_cta_and_lead_intent_flow() -> None:
    client = TestClient(app)
    api_key_name = "pytest.reader.intent"
    raw_key = _create_api_key(Scope.bot, api_key_name)
    telegram_user_id = 9_880_002
    post_id = None

    db = SessionLocal()
    try:
        post = ScheduledPost(
            title="Пилот AI в договорной функции",
            text="Пошаговый подход к запуску пилота без перегруза команды",
            rubric="legal_ops",
            publish_at=datetime.now(timezone.utc) - timedelta(hours=1),
            posted_at=datetime.now(timezone.utc) - timedelta(hours=1),
            status=ScheduledPostStatus.posted,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        post_id = post.id
    finally:
        db.close()

    try:
        feedback_response = client.post(
            "/api/v1/reader/feedback",
            json={
                "telegram_user_id": telegram_user_id,
                "post_id": str(post_id),
                "signal_key": "reader.useful",
                "signal_value": 1,
                "text": "Практично и по делу",
            },
            headers={"X-API-Key": raw_key},
        )
        assert feedback_response.status_code == 200
        feedback_payload = feedback_response.json()
        assert feedback_payload["post_id"] == str(post_id)
        assert feedback_payload["signal_key"] == "reader.useful"
        assert feedback_payload["signal_value"] == 1

        db = SessionLocal()
        try:
            post = db.get(ScheduledPost, post_id)
            assert post is not None
            assert post.feedback_snapshot is not None
            assert int(post.feedback_snapshot.get("comments_total", 0)) == 1
            assert int(post.feedback_snapshot.get("comments_positive", 0)) == 1
        finally:
            db.close()

        cta_response = client.post(
            "/api/v1/reader/cta-click",
            json={
                "telegram_user_id": telegram_user_id,
                "post_id": str(post_id),
                "cta_type": "consultation",
                "context": "reader_post",
            },
            headers={"X-API-Key": raw_key},
        )
        assert cta_response.status_code == 200
        assert cta_response.json()["message"] == "ok"

        create_lead_response = client.post(
            "/api/v1/reader/lead-intent",
            json={
                "telegram_user_id": telegram_user_id,
                "post_id": str(post_id),
                "intent_type": "consultation",
                "message": "Хочу обсудить внедрение",
                "name": "Reader User",
            },
            headers={"X-API-Key": raw_key},
        )
        assert create_lead_response.status_code == 200
        first_intent = create_lead_response.json()
        assert first_intent["created"] is True

        update_lead_response = client.post(
            "/api/v1/reader/lead-intent",
            json={
                "telegram_user_id": telegram_user_id,
                "post_id": str(post_id),
                "intent_type": "followup",
                "message": "Оставляю контакт",
                "contact": "@reader_contact",
            },
            headers={"X-API-Key": raw_key},
        )
        assert update_lead_response.status_code == 200
        second_intent = update_lead_response.json()
        assert second_intent["created"] is False
        assert second_intent["lead_id"] == first_intent["lead_id"]

        db = SessionLocal()
        try:
            lead = db.execute(
                select(Lead)
                .where(Lead.telegram_user_id == telegram_user_id)
                .order_by(Lead.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            assert lead is not None
            assert lead.contact == "@reader_contact"
            assert lead.notes is not None
            assert "[READER_REFERRAL] intent=consultation" in lead.notes
            assert "[READER_REFERRAL] intent=followup" in lead.notes

            lead_events = list(
                db.execute(select(Event).where(Event.type == "reader.lead_intent")).scalars().all()
            )
            assert any(item.lead_id == lead.id for item in lead_events)
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            db.execute(
                delete(Event).where(
                    Event.type.in_(["reader.cta_click", "reader.lead_intent"])
                )
            )
            db.execute(delete(Lead).where(Lead.telegram_user_id == telegram_user_id))
            if post_id is not None:
                db.execute(delete(PostFeedbackSignal).where(PostFeedbackSignal.post_id == post_id))
                db.execute(delete(ScheduledPost).where(ScheduledPost.id == post_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)
