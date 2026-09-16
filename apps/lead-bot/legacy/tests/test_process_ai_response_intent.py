"""process_ai_response: не-продажный интент отключает докрутку funnel.enforce_leadgen_response
(иначе стадийные добавки — «типичный сигнал…», форс-вопрос квалификации — портили ответ,
уже адаптированный под интент)."""
from types import SimpleNamespace

import pytest

import intent_router
from handlers import user_ai_response


def _base_mocks(monkeypatch, *, intent_result):
    monkeypatch.setattr(user_ai_response.database.db, "add_message", lambda *a, **k: None)
    monkeypatch.setattr(user_ai_response.database.db, "get_conversation_history", lambda user_id: [])
    monkeypatch.setattr(user_ai_response.database.db, "update_user_funnel_state", lambda *a, **k: None)
    monkeypatch.setattr(user_ai_response.database.db, "update_lead_funnel_state", lambda *a, **k: None)
    monkeypatch.setattr(user_ai_response.database.db, "update_lead_last_message_time", lambda *a, **k: None)
    monkeypatch.setattr(user_ai_response.database.db, "track_event", lambda *a, **k: None)
    monkeypatch.setattr(user_ai_response.funnel, "infer_stage", lambda **kwargs: "discover")
    monkeypatch.setattr(user_ai_response.funnel, "is_cta_shown", lambda *a, **k: False)
    monkeypatch.setattr(user_ai_response, "_schedule_post_response_lead_processing", lambda **kwargs: None)
    monkeypatch.setattr(user_ai_response, "_track_tokens", lambda **kwargs: None)

    async def _fake_maybe_cta(**kwargs):
        return False

    monkeypatch.setattr(user_ai_response, "_maybe_send_consultation_cta", _fake_maybe_cta)

    async def _fake_deliver(**kwargs):
        return None

    monkeypatch.setattr(user_ai_response, "_deliver_final_response", _fake_deliver)

    async def _fake_stream(**kwargs):
        return "Ответ помощника", None, intent_result

    monkeypatch.setattr(user_ai_response, "_stream_response_text", _fake_stream)


@pytest.mark.asyncio
async def test_sales_intent_still_runs_leadgen_enforcement(monkeypatch):
    calls = []
    monkeypatch.setattr(
        user_ai_response.funnel,
        "enforce_leadgen_response",
        lambda **kwargs: (calls.append(kwargs) or kwargs["response_text"]),
    )
    _base_mocks(
        monkeypatch,
        intent_result=intent_router.IntentResult(intent="sales_conversation", confidence=0.0, context_override=None),
    )

    await user_ai_response.process_ai_response(
        update=SimpleNamespace(),
        context=SimpleNamespace(),
        original_message=SimpleNamespace(),
        user=SimpleNamespace(first_name="Иван", id=1),
        user_data={"id": 1, "telegram_id": 1, "first_name": "Иван"},
        lead=None,
        message_text="Хочу автоматизировать договорную работу",
        current_stage="discover",
        cta_variant="A",
        cta_shown=False,
        allow_lead_processing=True,
    )

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_non_sales_intent_skips_leadgen_enforcement(monkeypatch):
    calls = []
    monkeypatch.setattr(
        user_ai_response.funnel,
        "enforce_leadgen_response",
        lambda **kwargs: (calls.append(kwargs) or kwargs["response_text"]),
    )
    _base_mocks(
        monkeypatch,
        intent_result=intent_router.IntentResult(
            intent="platform_question", confidence=0.9, context_override="# Вопрос о платформе\n..."
        ),
    )

    await user_ai_response.process_ai_response(
        update=SimpleNamespace(),
        context=SimpleNamespace(),
        original_message=SimpleNamespace(),
        user=SimpleNamespace(first_name="Гость", id=2),
        user_data={"id": 2, "telegram_id": 2, "first_name": "Гость"},
        lead=None,
        message_text="Сколько стоит ваша система?",
        current_stage="discover",
        cta_variant="A",
        cta_shown=False,
        allow_lead_processing=True,
    )

    assert calls == []
