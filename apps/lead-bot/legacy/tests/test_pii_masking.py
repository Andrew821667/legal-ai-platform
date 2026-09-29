"""Персональные данные не уходят к вендору модели (pii.py).

Модель видит метки [ИМЯ_1], [ТЕЛЕФОН_1]…; клиент получает ответ с настоящими
значениями, инструменты — настоящие аргументы.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import pii
from tests.test_ai_brain_function_calling import (
    _FakeClient,
    _FakeStreamingCompletions,
    _collect,
    _content_chunk,
    _finish_chunk,
    _make_brain,
    _tool_call_chunk,
)

_SHARED = Path(__file__).resolve().parents[4] / "packages" / "shared" / "shared" / "pii.py"


@pytest.mark.skipif(not _SHARED.exists(), reason="нет packages/shared рядом (образ бота)")
def test_bot_copy_matches_the_shared_module() -> None:
    # У бота свой образ без packages/shared — копия должна совпадать с ядром.
    assert (Path(__file__).resolve().parents[1] / "pii.py").read_text() == _SHARED.read_text()


def _sent_text(call: dict) -> str:
    return json.dumps(call["messages"], ensure_ascii=False)


@pytest.mark.asyncio
async def test_model_sees_placeholders_client_sees_real_values(monkeypatch: pytest.MonkeyPatch) -> None:
    brain = _make_brain(monkeypatch)
    completions = _FakeStreamingCompletions(
        [[_content_chunk("Спасибо, [ИМ"), _content_chunk("Я_1]! Перезвоним на [ТЕЛЕФОН_1]."), _finish_chunk("stop")]]
    )
    brain.async_client = _FakeClient(completions)

    result = await _collect(
        brain.generate_response_stream(
            [{"role": "user", "message": "Меня зовут Лейла Каримова, телефон +7 999 123-45-67."}],
            funnel_context="# Данные клиента\nКлиент: Лейла Каримова, договор AV-2026-017.",
            known_names=("Лейла",),
        )
    )

    sent = _sent_text(completions.calls[0])
    assert "Лейла" not in sent and "Каримова" not in sent and "123-45-67" not in sent
    assert "[ИМЯ_1]" in sent and pii.MASK_NOTE in sent
    # Наш системный промпт уходит без изменений.
    assert completions.calls[0]["messages"][0]["content"] == ai_brain_prompt()
    # Известное имя — своя метка, фамилия — своя; модель назвала только имя.
    assert result == "Спасибо, Лейла! Перезвоним на +7 999 123-45-67."


def ai_brain_prompt() -> str:
    import prompts

    return prompts.SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_tool_gets_real_arguments_and_its_result_is_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    brain = _make_brain(monkeypatch)
    completions = _FakeStreamingCompletions(
        [
            [
                _tool_call_chunk(0, tool_id="call_1", name="identify_returning_client", arguments='{"contact": "[ТЕЛЕФОН_1]"}'),
                _finish_chunk("tool_calls"),
            ],
            [_content_chunk("Нашёл ваше дело.", "stop")],
        ]
    )
    brain.async_client = _FakeClient(completions)
    seen: list[dict] = []

    async def executor(name: str, arguments: dict) -> str:
        seen.append(arguments)
        return "Клиент: Петров Иван Сергеевич, почта petrov@example.ru"

    await _collect(
        brain.generate_response_stream(
            [{"role": "user", "message": "Я уже клиент, мой номер +79991234567"}],
            tools=[{"type": "function", "function": {"name": "identify_returning_client"}}],
            tool_executor=executor,
        )
    )

    assert seen == [{"contact": "+79991234567"}]
    second_round = _sent_text(completions.calls[1])
    assert "Петров" not in second_round and "petrov@example.ru" not in second_round


@pytest.mark.asyncio
async def test_lead_extraction_returns_real_contacts(monkeypatch: pytest.MonkeyPatch) -> None:
    brain = _make_brain(monkeypatch)
    sent: list[dict] = []

    class _Completions:
        async def create(self, **kwargs):
            sent.append(kwargs)

            class _Message:
                content = '{"name": "[ИМЯ_1]", "phone": "[ТЕЛЕФОН_1]", "lead_temperature": "warm"}'

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

    brain.async_client = _FakeClient(_Completions())
    data = await brain.extract_lead_data_async(
        [{"role": "user", "content": "Меня зовут Иван Петров, мой телефон 8 999 123 45 67"}],
    )

    assert "Иван" not in _sent_text(sent[0]) and "123 45 67" not in _sent_text(sent[0])
    # Телефон разбор приводит к +7…: главное, что вернулось настоящее значение, а не метка.
    assert data["name"] == "Иван Петров" and data["phone"] == "+79991234567"


@pytest.mark.asyncio
async def test_masking_switch_off(monkeypatch: pytest.MonkeyPatch) -> None:
    import ai_brain

    monkeypatch.setattr(ai_brain.config, "LLM_PII_MASKING_ENABLED", False)
    brain = _make_brain(monkeypatch)
    completions = _FakeStreamingCompletions([[_content_chunk("ok", "stop")]])
    brain.async_client = _FakeClient(completions)

    await _collect(brain.generate_response_stream([{"role": "user", "message": "Меня зовут Иван Петров."}]))

    assert "Иван Петров" in _sent_text(completions.calls[0])


def test_no_separate_transborder_consent_any_more() -> None:
    # С обезличиванием данные за рубеж не уходят — отдельного согласия и шага
    # «разрешите ИИ-режим» перед ответом ассистента больше нет.
    import inspect

    import content
    from handlers import user

    assert "transborder" not in inspect.getsource(user.handle_message).lower()
    assert content.consent_user_status_text({"consent_given": True}) == "✅ Согласие на обработку ПД уже дано."
    assert "обезличенный текст" in content.transborder_policy_text()
