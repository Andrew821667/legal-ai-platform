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
