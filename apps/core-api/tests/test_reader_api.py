from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect as sa_inspect, select

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    Event,
    Lead,
    PostFeedbackSignal,
    ReaderMiniAppEvent,
    ReaderEventRollup,
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


def _rollup_table_exists(db) -> bool:
    try:
        return bool(sa_inspect(db.get_bind()).has_table("reader_event_rollups"))
    except Exception:
        return False


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


def test_reader_miniapp_profile_events_and_deeplink() -> None:
    client = TestClient(app)
    api_key_name = "pytest.reader.miniapp"
    raw_key = _create_api_key(Scope.news, api_key_name)
    telegram_user_id = 9_880_000 + int(datetime.now(timezone.utc).timestamp() % 100000)

    try:
        get_response = client.get(
            f"/api/v1/reader/miniapp/profile?telegram_user_id={telegram_user_id}",
            headers={"X-API-Key": raw_key},
        )
        assert get_response.status_code == 200
        assert get_response.json()["telegram_user_id"] == telegram_user_id
        assert get_response.json()["onboarding_done"] is False

        patch_response = client.patch(
            "/api/v1/reader/miniapp/profile",
            json={
                "telegram_user_id": telegram_user_id,
                "onboarding_done": True,
                "audience": "lawyer",
                "interests": ["ai_law", "contracts", "AI_LAW"],
                "goal": "Сократить цикл проверки договоров",
                "last_action": "miniapp_profile_saved",
                "sync_reader_topics": True,
                "digest_frequency": "weekly",
            },
            headers={"X-API-Key": raw_key},
        )
        assert patch_response.status_code == 200
        patched = patch_response.json()
        assert patched["onboarding_done"] is True
        assert patched["audience"] == "lawyer"
        assert patched["interests"] == ["ai_law", "contracts"]
        assert patched["topics"] == ["ai_law", "contracts"]
        assert patched["last_action"] == "profile.saved"

        event_response = client.post(
            "/api/v1/reader/miniapp/event",
            json={
                "telegram_user_id": telegram_user_id,
                "event_type": "action",
                "source": "miniapp",
                "screen": "/miniapp/content",
                "action": "miniapp_content_open_contract_ai",
                "payload": {"source": "test"},
            },
            headers={"X-API-Key": raw_key},
        )
        assert event_response.status_code == 200
        event_payload = event_response.json()
        assert event_payload["telegram_user_id"] == telegram_user_id
        assert event_payload["event_type"] == "action"
        assert event_payload["source"] == "miniapp.app"
        assert event_payload["action"] == "open.contract_ai"
        assert event_payload["payload"]["cta_variant"] in {"v1_direct", "v2_diagnostic"}

        events_response = client.get(
            f"/api/v1/reader/miniapp/events?telegram_user_id={telegram_user_id}&limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert events_response.status_code == 200
        events = events_response.json()
        assert len(events) >= 1
        assert events[0]["telegram_user_id"] == telegram_user_id

        profile_after_event = client.get(
            f"/api/v1/reader/miniapp/profile?telegram_user_id={telegram_user_id}",
            headers={"X-API-Key": raw_key},
        )
        assert profile_after_event.status_code == 200
        assert profile_after_event.json()["last_action"] == "open.contract_ai"

        deeplink_response = client.post(
            "/api/v1/reader/miniapp/deeplink",
            json={
                "telegram_user_id": telegram_user_id,
                "source": "reader_bot",
                "screen": "content",
                "action": "open_saved",
            },
            headers={"X-API-Key": raw_key},
        )
        assert deeplink_response.status_code == 200
        deeplink = deeplink_response.json()
        assert deeplink["path"] == "/miniapp/content"
        assert f"tg={telegram_user_id}" in deeplink["url"]
        assert deeplink["query"]["screen"] == "content"
        assert deeplink["query"]["src"] == "reader.bot"
        assert deeplink["query"]["act"] == "open.saved"

        summary_response = client.get(
            "/api/v1/reader/miniapp/events/summary?hours=48&limit_users=5",
            headers={"X-API-Key": raw_key},
        )
        assert summary_response.status_code == 200
        summary = summary_response.json()
        assert summary["hours"] == 48
        assert summary["total_events"] >= 2
        assert summary["unique_users"] >= 1
        assert any(item["label"] == "miniapp.app" for item in summary["top_sources"])
        assert any(item["telegram_user_id"] == telegram_user_id for item in summary["top_users"])
        assert len(summary["recent_events"]) >= 2
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ReaderMiniAppEvent).where(ReaderMiniAppEvent.telegram_user_id == telegram_user_id))
            db.execute(delete(ReaderSavedPost).where(ReaderSavedPost.telegram_user_id == telegram_user_id))
            db.execute(delete(ReaderPreference).where(ReaderPreference.telegram_user_id == telegram_user_id))
            db.execute(
                delete(Event).where(
                    Event.type.in_(
                        ["reader.miniapp.event", "reader.miniapp.deeplink", "reader.cta_click", "reader.lead_intent"]
                    )
                )
            )
            if _rollup_table_exists(db):
                db.execute(delete(ReaderEventRollup))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_reader_conversion_funnel_endpoint() -> None:
    client = TestClient(app)
    api_key_name = "pytest.reader.funnel"
    raw_key = _create_api_key(Scope.news, api_key_name)
    user_a = 9_880_101
    user_b = 9_880_102

    try:
        event_a = client.post(
            "/api/v1/reader/miniapp/event",
            json={
                "telegram_user_id": user_a,
                "event_type": "nav_click",
                "source": "miniapp_home",
                "screen": "home",
                "action": "miniapp_home_open_content",
                "payload": {},
            },
            headers={"X-API-Key": raw_key},
        )
        assert event_a.status_code == 200

        event_b = client.post(
            "/api/v1/reader/miniapp/event",
            json={
                "telegram_user_id": user_b,
                "event_type": "cta_click",
                "source": "miniapp_flow",
                "screen": "/miniapp",
                "action": "miniapp_flow_open_lead_bot",
                "payload": {},
            },
            headers={"X-API-Key": raw_key},
        )
        assert event_b.status_code == 200

        cta_a = client.post(
            "/api/v1/reader/cta-click",
            json={
                "telegram_user_id": user_a,
                "cta_type": "consultation",
                "context": "reader_post",
                "payload": {"action": "cta.consultation"},
            },
            headers={"X-API-Key": raw_key},
        )
        assert cta_a.status_code == 200

        cta_b = client.post(
            "/api/v1/reader/cta-click",
            json={
                "telegram_user_id": user_b,
                "cta_type": "miniapp_open",
                "context": "reader_nav",
                "payload": {"action": "open.miniapp.home"},
            },
            headers={"X-API-Key": raw_key},
        )
        assert cta_b.status_code == 200

        intent_a = client.post(
            "/api/v1/reader/lead-intent",
            json={
                "telegram_user_id": user_a,
                "intent_type": "consultation",
                "message": "Нужен пилот",
                "payload": {"source": "reader_bot", "action": "lead.consultation"},
            },
            headers={"X-API-Key": raw_key},
        )
        assert intent_a.status_code == 200
        assert intent_a.json()["created"] is True

        funnel_response = client.get(
            "/api/v1/reader/conversion-funnel?hours=168",
            headers={"X-API-Key": raw_key},
        )
        assert funnel_response.status_code == 200
        funnel = funnel_response.json()
        assert funnel["hours"] == 168
        assert funnel["unique_users_total"] >= 2
        assert funnel["leads_total"] >= 1

        stages = {item["key"]: item["users"] for item in funnel["stages"]}
        assert stages["miniapp_active"] >= 2
        assert stages["cta_click"] >= 2
        assert stages["lead_intent"] >= 1

        rates = {item["key"]: item["value"] for item in funnel["rates"]}
        assert rates["miniapp_to_cta"] >= 0.0
        assert rates["cta_to_intent"] >= 0.0
        assert rates["miniapp_to_intent"] >= 0.0

        assert any(item["label"] == "miniapp.home" for item in funnel["top_miniapp_sources"])
        assert any(item["label"] == "reader.post" for item in funnel["top_cta_sources"])
        assert any(item["label"] == "reader.bot" for item in funnel["top_intent_sources"])
        assert any(item["label"] == "open.content" for item in funnel["top_actions"])
        assert funnel["variants"]
        assert any(item["cta_variant"] in {"v1_direct", "v2_diagnostic"} for item in funnel["variants"])

        db = SessionLocal()
        try:
            if _rollup_table_exists(db):
                rollups = list(db.execute(select(ReaderEventRollup)).scalars().all())
                assert any(item.channel == "miniapp" for item in rollups)
                assert any(item.channel == "cta" for item in rollups)
                assert any(item.channel == "intent" for item in rollups)
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ReaderMiniAppEvent).where(ReaderMiniAppEvent.telegram_user_id.in_([user_a, user_b])))
            db.execute(delete(ReaderSavedPost).where(ReaderSavedPost.telegram_user_id.in_([user_a, user_b])))
            db.execute(delete(ReaderPreference).where(ReaderPreference.telegram_user_id.in_([user_a, user_b])))
            db.execute(delete(Event).where(Event.type.in_(["reader.cta_click", "reader.lead_intent"])))
            db.execute(delete(Lead).where(Lead.telegram_user_id.in_([user_a, user_b])))
            if _rollup_table_exists(db):
                db.execute(delete(ReaderEventRollup))
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
            assert any((item.payload or {}).get("source") == "reader.bot" for item in lead_events)
            cta_events = list(db.execute(select(Event).where(Event.type == "reader.cta_click")).scalars().all())
            assert any((item.payload or {}).get("context") == "reader.post" for item in cta_events)
            assert any((item.payload or {}).get("action") == "cta.consultation" for item in cta_events)
            assert all((item.payload or {}).get("cta_variant") for item in cta_events)
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
            if _rollup_table_exists(db):
                db.execute(delete(ReaderEventRollup))
            if post_id is not None:
                db.execute(delete(PostFeedbackSignal).where(PostFeedbackSignal.post_id == post_id))
                db.execute(delete(ScheduledPost).where(ScheduledPost.id == post_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_reader_continue_state_flow() -> None:
    client = TestClient(app)
    api_key_name = "pytest.reader.continue_state"
    raw_key = _create_api_key(Scope.news, api_key_name)
    telegram_user_id = 9_800_000 + int(datetime.now(timezone.utc).timestamp() % 100000)
    post_id = None

    db = SessionLocal()
    try:
        post = ScheduledPost(
            title="Контрактный разбор: пилот AI",
            text="Короткий практический материал по проверке договора",
            rubric="contracts",
            publish_at=datetime.now(timezone.utc) - timedelta(hours=2),
            posted_at=datetime.now(timezone.utc) - timedelta(hours=2),
            status=ScheduledPostStatus.posted,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        post_id = post.id
    finally:
        db.close()

    try:
        state_response = client.get(
            f"/api/v1/reader/continue-state?telegram_user_id={telegram_user_id}",
            headers={"X-API-Key": raw_key},
        )
        assert state_response.status_code == 200
        initial_state = state_response.json()
        assert initial_state["onboarding_done"] is False
        assert initial_state["recommended_section"] == "profile"

        patch_response = client.patch(
            "/api/v1/reader/miniapp/profile",
            json={
                "telegram_user_id": telegram_user_id,
                "onboarding_done": True,
                "audience": "lawyer",
                "interests": ["contracts", "ai_law"],
                "last_action": "miniapp_content_open_contract_ai",
            },
            headers={"X-API-Key": raw_key},
        )
        assert patch_response.status_code == 200

        save_response = client.post(
            "/api/v1/reader/save",
            json={
                "telegram_user_id": telegram_user_id,
                "post_id": str(post_id),
                "saved": True,
            },
            headers={"X-API-Key": raw_key},
        )
        assert save_response.status_code == 200
        assert save_response.json()["saved"] is True

        lead_intent_response = client.post(
            "/api/v1/reader/lead-intent",
            json={
                "telegram_user_id": telegram_user_id,
                "post_id": str(post_id),
                "intent_type": "consultation",
                "message": "Нужен формат внедрения",
            },
            headers={"X-API-Key": raw_key},
        )
        assert lead_intent_response.status_code == 200

        final_state_response = client.get(
            f"/api/v1/reader/continue-state?telegram_user_id={telegram_user_id}",
            headers={"X-API-Key": raw_key},
        )
        assert final_state_response.status_code == 200
        final_state = final_state_response.json()
        assert final_state["onboarding_done"] is True
        assert final_state["saved_count"] >= 1
        assert final_state["lead_intents_30d"] >= 1
        assert final_state["recommended_section"] == "solutions"
        assert final_state["recommended_screen"] == "solutions"
        assert isinstance(final_state["recommended_reason"], str) and final_state["recommended_reason"]
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ReaderMiniAppEvent).where(ReaderMiniAppEvent.telegram_user_id == telegram_user_id))
            db.execute(delete(ReaderSavedPost).where(ReaderSavedPost.telegram_user_id == telegram_user_id))
            db.execute(delete(ReaderPreference).where(ReaderPreference.telegram_user_id == telegram_user_id))
            db.execute(delete(Event).where(Event.type == "reader.lead_intent"))
            db.execute(delete(Lead).where(Lead.telegram_user_id == telegram_user_id))
            if _rollup_table_exists(db):
                db.execute(delete(ReaderEventRollup))
            if post_id is not None:
                db.execute(delete(PostFeedbackSignal).where(PostFeedbackSignal.post_id == post_id))
                db.execute(delete(ScheduledPost).where(ScheduledPost.id == post_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)
