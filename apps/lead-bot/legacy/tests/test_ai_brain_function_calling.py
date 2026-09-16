"""generate_response_stream с function calling: без tools/tool_executor — поведение
не меняется вообще; с ними — накопление стриминговых tool_calls по index, исполнение,
продолжение диалога результатом инструмента, потолок раундов, устойчивость к сбоям."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

import ai_brain as ai_brain_module


@dataclass
class _FakeToolCallFunction:
    name: str | None = None
    arguments: str | None = None


@dataclass
class _FakeToolCallDelta:
    index: int
    id: str | None = None
    function: _FakeToolCallFunction | None = None


@dataclass
class _FakeDelta:
    content: str | None = None
    tool_calls: list[_FakeToolCallDelta] | None = None


@dataclass
class _FakeStreamChoice:
    delta: _FakeDelta
    finish_reason: str | None = None


@dataclass
class _FakeStreamChunk:
    choices: list[_FakeStreamChoice]


def _content_chunk(text: str, finish_reason: str | None = None) -> _FakeStreamChunk:
    return _FakeStreamChunk(choices=[_FakeStreamChoice(delta=_FakeDelta(content=text), finish_reason=finish_reason)])


def _finish_chunk(finish_reason: str) -> _FakeStreamChunk:
    return _FakeStreamChunk(choices=[_FakeStreamChoice(delta=_FakeDelta(), finish_reason=finish_reason)])


def _tool_call_chunk(index: int, *, tool_id: str | None = None, name: str | None = None, arguments: str | None = None) -> _FakeStreamChunk:
    return _FakeStreamChunk(
        choices=[
            _FakeStreamChoice(
                delta=_FakeDelta(tool_calls=[_FakeToolCallDelta(index=index, id=tool_id, function=_FakeToolCallFunction(name=name, arguments=arguments))]),
                finish_reason=None,
            )
        ]
    )


class _FakeStream:
    def __init__(self, chunks: list[_FakeStreamChunk]) -> None:
        self._chunks = chunks

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStreamingCompletions:
    """Каждый вызов .create() отдаёт следующий заранее заготовленный раунд."""

    def __init__(self, rounds: list[list[_FakeStreamChunk]]) -> None:
        self._rounds = rounds
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeStream:
        self.calls.append(kwargs)
        chunks = self._rounds[len(self.calls) - 1]
        return _FakeStream(chunks)


class _FakeChat:
    def __init__(self, completions: Any) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, completions: Any) -> None:
        self.chat = _FakeChat(completions)


def _make_brain(monkeypatch: pytest.MonkeyPatch) -> ai_brain_module.AIBrain:
    monkeypatch.setattr(ai_brain_module.database.db, "get_successful_conversations", lambda limit=30: [])
    return ai_brain_module.AIBrain()


async def _collect(agen):
    return "".join([chunk async for chunk in agen])


@pytest.mark.asyncio
async def test_no_tools_behaves_exactly_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    brain = _make_brain(monkeypatch)
    completions = _FakeStreamingCompletions([[_content_chunk("Привет"), _content_chunk(", клиент", "stop")]])
    brain.async_client = _FakeClient(completions)

    result = await _collect(brain.generate_response_stream([{"role": "user", "message": "Привет"}]))

    assert result == "Привет, клиент"
    assert len(completions.calls) == 1
    assert "tools" not in completions.calls[0]


@pytest.mark.asyncio
async def test_tools_without_executor_are_not_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """tools передали, а tool_executor — нет: без исполнителя звать нечего, tools не уходят."""
    brain = _make_brain(monkeypatch)
    completions = _FakeStreamingCompletions([[_content_chunk("Ответ", "stop")]])
    brain.async_client = _FakeClient(completions)

    await _collect(
        brain.generate_response_stream(
            [{"role": "user", "message": "Привет"}],
            tools=[{"type": "function", "function": {"name": "noop"}}],
            tool_executor=None,
        )
    )

    assert "tools" not in completions.calls[0]


@pytest.mark.asyncio
async def test_tool_call_is_executed_and_result_continues_the_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    brain = _make_brain(monkeypatch)
    completions = _FakeStreamingCompletions(
        [
            # Раунд 1: модель зовёт инструмент, аргументы приходят по частям.
            [
                _tool_call_chunk(0, tool_id="call_1", name="get_full_case_details", arguments=""),
                _tool_call_chunk(0, arguments='{"why"'),
                _tool_call_chunk(0, arguments=': "уточнить"}'),
                _finish_chunk("tool_calls"),
            ],
            # Раунд 2: модель отвечает с учётом результата инструмента.
            [_content_chunk("По вашему делу: ", None), _content_chunk("статус — в работе.", "stop")],
        ]
    )
    brain.async_client = _FakeClient(completions)

    tool_calls_seen: list[tuple[str, dict]] = []

    async def _executor(name: str, arguments: dict) -> str:
        tool_calls_seen.append((name, arguments))
        return "Обращение от 07.09, статус: в работе."

    result = await _collect(
        brain.generate_response_stream(
            [{"role": "user", "message": "Какой статус по моему делу?"}],
            tools=[{"type": "function", "function": {"name": "get_full_case_details"}}],
            tool_executor=_executor,
        )
    )

    assert result == "По вашему делу: статус — в работе."
    assert tool_calls_seen == [("get_full_case_details", {"why": "уточнить"})]
    assert len(completions.calls) == 2
    assert completions.calls[0]["tools"]
    # Второй запрос содержит assistant-сообщение с tool_calls и tool-результат.
    second_messages = completions.calls[1]["messages"]
    roles = [m["role"] for m in second_messages]
    assert "assistant" in roles and "tool" in roles
    tool_message = next(m for m in second_messages if m["role"] == "tool")
    assert tool_message["tool_call_id"] == "call_1"
    assert tool_message["content"] == "Обращение от 07.09, статус: в работе."


@pytest.mark.asyncio
async def test_tool_executor_exception_does_not_break_the_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    brain = _make_brain(monkeypatch)
    completions = _FakeStreamingCompletions(
        [
            [_tool_call_chunk(0, tool_id="call_1", name="get_full_case_details", arguments="{}"), _finish_chunk("tool_calls")],
            [_content_chunk("Отвечу без этих данных.", "stop")],
        ]
    )
    brain.async_client = _FakeClient(completions)

    async def _boom(name: str, arguments: dict) -> str:
        raise RuntimeError("core-api unreachable")

    result = await _collect(
        brain.generate_response_stream(
            [{"role": "user", "message": "Что по делу?"}],
            tools=[{"type": "function", "function": {"name": "get_full_case_details"}}],
            tool_executor=_boom,
        )
    )

    assert result == "Отвечу без этих данных."
    tool_message = next(m for m in completions.calls[1]["messages"] if m["role"] == "tool")
    assert tool_message["content"] == "Инструмент временно недоступен."


@pytest.mark.asyncio
async def test_malformed_tool_arguments_json_falls_back_to_empty_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    brain = _make_brain(monkeypatch)
    completions = _FakeStreamingCompletions(
        [
            [_tool_call_chunk(0, tool_id="call_1", name="get_full_case_details", arguments="не json"), _finish_chunk("tool_calls")],
            [_content_chunk("Ок.", "stop")],
        ]
    )
    brain.async_client = _FakeClient(completions)

    seen_args = {}

    async def _executor(name: str, arguments: dict) -> str:
        seen_args.update(arguments)
        seen_args["_called"] = True
        return "готово"

    await _collect(
        brain.generate_response_stream(
            [{"role": "user", "message": "?"}],
            tools=[{"type": "function", "function": {"name": "get_full_case_details"}}],
            tool_executor=_executor,
        )
    )

    assert seen_args == {"_called": True}


@pytest.mark.asyncio
async def test_repeated_tool_calls_hit_round_limit_and_yield_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    brain = _make_brain(monkeypatch)
    # Модель каждый раз просит инструмент — раундов ровно _MAX_TOOL_ROUNDS.
    one_round = [_tool_call_chunk(0, tool_id="call_x", name="get_full_case_details", arguments="{}"), _finish_chunk("tool_calls")]
    completions = _FakeStreamingCompletions([one_round for _ in range(ai_brain_module._MAX_TOOL_ROUNDS)])
    brain.async_client = _FakeClient(completions)

    async def _executor(name: str, arguments: dict) -> str:
        return "снова данные"

    result = await _collect(
        brain.generate_response_stream(
            [{"role": "user", "message": "?"}],
            tools=[{"type": "function", "function": {"name": "get_full_case_details"}}],
            tool_executor=_executor,
        )
    )

    assert "Не получилось получить ответ инструмента" in result
    assert len(completions.calls) == ai_brain_module._MAX_TOOL_ROUNDS


@pytest.mark.asyncio
async def test_llm_error_still_yields_fallback_message(monkeypatch: pytest.MonkeyPatch) -> None:
    brain = _make_brain(monkeypatch)

    class _Boom:
        async def create(self, **kwargs):
            raise RuntimeError("network down")

    brain.async_client = _FakeClient(_Boom())

    result = await _collect(brain.generate_response_stream([{"role": "user", "message": "Привет"}]))

    assert "ошибка" in result.lower()
