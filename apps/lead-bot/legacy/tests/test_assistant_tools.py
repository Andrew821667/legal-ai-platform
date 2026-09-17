"""assistant_tools.py: схема, диспетчер, устойчивость к сбоям — первый
инструмент ассистента (пункт 2 плана «умный ассистент»)."""
import pytest

import assistant_tools


def test_tools_schema_shape():
    assert len(assistant_tools.TOOLS_SCHEMA) == 1
    tool = assistant_tools.TOOLS_SCHEMA[0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "get_full_case_details"
    assert "description" in tool["function"] and len(tool["function"]["description"]) > 20
    assert tool["function"]["parameters"]["type"] == "object"


@pytest.mark.asyncio
async def test_execute_dispatches_to_platform_context(monkeypatch):
    monkeypatch.setattr(
        assistant_tools.platform_context,
        "build_full_case_details_block",
        lambda telegram_id: f"полные данные для {telegram_id}",
    )

    result = await assistant_tools.execute("get_full_case_details", {}, telegram_id=275782221)

    assert result == "полные данные для 275782221"


@pytest.mark.asyncio
async def test_execute_unknown_tool_name():
    result = await assistant_tools.execute("delete_everything", {}, telegram_id=1)
    assert "не существует" in result


@pytest.mark.asyncio
async def test_execute_swallows_exceptions(monkeypatch):
    def _boom(telegram_id):
        raise RuntimeError("core-api down")

    monkeypatch.setattr(assistant_tools.platform_context, "build_full_case_details_block", _boom)

    result = await assistant_tools.execute("get_full_case_details", {}, telegram_id=1)

    assert "Не удалось" in result


@pytest.mark.asyncio
async def test_executor_for_binds_telegram_id(monkeypatch):
    seen = {}

    def _fake(telegram_id):
        seen["id"] = telegram_id
        return "ok"

    monkeypatch.setattr(assistant_tools.platform_context, "build_full_case_details_block", _fake)

    executor = assistant_tools.executor_for(999)
    result = await executor("get_full_case_details", {})

    assert seen["id"] == 999
    assert result == "ok"


def test_identify_returning_client_tool_shape():
    tool = assistant_tools.IDENTIFY_RETURNING_CLIENT_TOOL
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "identify_returning_client"
    required = tool["function"]["parameters"]["required"]
    assert set(required) == {"contact", "agreement_number"}
    # Не входит в общую схему Telegram — только веб-виджет собирает её сам.
    assert tool not in assistant_tools.TOOLS_SCHEMA


@pytest.mark.asyncio
async def test_executor_for_web_sets_state_on_successful_identification(monkeypatch):
    monkeypatch.setattr(
        assistant_tools.core_api_bridge.core_api_bridge,
        "verify_returning_client",
        lambda *, contact, agreement_number: 72001,
    )

    state = assistant_tools.WebSessionState()
    executor = assistant_tools.executor_for_web(state)
    result = await executor(
        "identify_returning_client",
        {"contact": "+79092330909", "agreement_number": "P-001"},
    )

    assert "Подтверждено" in result
    assert state.telegram_id == 72001


@pytest.mark.asyncio
async def test_executor_for_web_leaves_state_none_when_not_verified(monkeypatch):
    monkeypatch.setattr(
        assistant_tools.core_api_bridge.core_api_bridge,
        "verify_returning_client",
        lambda *, contact, agreement_number: None,
    )

    state = assistant_tools.WebSessionState()
    executor = assistant_tools.executor_for_web(state)
    result = await executor(
        "identify_returning_client",
        {"contact": "+79990000000", "agreement_number": "P-999"},
    )

    assert state.telegram_id is None
    assert "Не сообщай собеседнику" in result  # это инструкция модели, не текст пользователю


@pytest.mark.asyncio
async def test_executor_for_web_requires_both_arguments():
    state = assistant_tools.WebSessionState()
    executor = assistant_tools.executor_for_web(state)

    result = await executor("identify_returning_client", {"contact": "+79092330909"})

    assert "Не хватает" in result
    assert state.telegram_id is None


@pytest.mark.asyncio
async def test_executor_for_web_swallows_verify_exceptions(monkeypatch):
    def _boom(*, contact, agreement_number):
        raise RuntimeError("core-api down")

    monkeypatch.setattr(assistant_tools.core_api_bridge.core_api_bridge, "verify_returning_client", _boom)

    state = assistant_tools.WebSessionState()
    executor = assistant_tools.executor_for_web(state)
    result = await executor(
        "identify_returning_client",
        {"contact": "+79092330909", "agreement_number": "P-001"},
    )

    assert "Не удалось" in result
    assert state.telegram_id is None


@pytest.mark.asyncio
async def test_executor_for_web_lets_get_full_case_details_see_identified_id(monkeypatch):
    """Ключевой сценарий: identify_returning_client и get_full_case_details
    вызваны в одном и том же ответе (модель сама решила проверить, затем
    сразу поднять детали) — второй инструмент должен увидеть telegram_id,
    который только что нашёл первый, а не None, с которым начался разговор."""
    monkeypatch.setattr(
        assistant_tools.core_api_bridge.core_api_bridge,
        "verify_returning_client",
        lambda *, contact, agreement_number: 72001,
    )
    seen = {}

    def _fake_details(telegram_id):
        seen["id"] = telegram_id
        return "детали дела"

    monkeypatch.setattr(assistant_tools.platform_context, "build_full_case_details_block", _fake_details)

    state = assistant_tools.WebSessionState()
    executor = assistant_tools.executor_for_web(state)
    await executor(
        "identify_returning_client",
        {"contact": "+79092330909", "agreement_number": "P-001"},
    )
    result = await executor("get_full_case_details", {})

    assert seen["id"] == 72001
    assert result == "детали дела"
