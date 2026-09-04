"""Разбор юридического обращения моделью.

Разбор готовит работу юриста, а не заменяет её: он называет область права,
срочность и недостающие документы, но не даёт правовых оценок. Сбой разбора не
должен мешать приёму обращения — уведомление уходит в любом случае.
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from core_api.intake_analysis import (
    DEFAULT_MODEL,
    MODEL_PRICING,
    SYSTEM_PROMPT,
    analyze_intake,
    estimate_cost,
    format_cost,
)

INTAKE = {"description": "Поставщик сорвал сроки на два месяца, предоплата внесена."}


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None


class _Opener:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.request = None

    def open(self, request, timeout=None):
        self.request = request
        return _Response(self.payload)


def _answer(text: str = "разбор", prompt: int = 100, completion: int = 200) -> dict:
    return {
        "model": DEFAULT_MODEL,
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
    }


def test_cost_is_computed_from_model_pricing() -> None:
    price_in, price_out = MODEL_PRICING[DEFAULT_MODEL]
    expected = (1000 * price_in + 500 * price_out) / 1_000_000

    assert estimate_cost(DEFAULT_MODEL, 1000, 500) == pytest.approx(expected)


def test_unknown_model_costs_nothing_instead_of_crashing() -> None:
    """Новая модель не должна ронять разбор: цену уточним, отчёт важнее."""
    assert estimate_cost("gpt-99-unknown", 1000, 500) == 0.0


def test_cost_is_formatted_with_five_decimals() -> None:
    """Суммы измеряются тысячными долями цента — округление скрыло бы их."""
    assert format_cost(0.005771) == "$0.00577"
    assert format_cost(0.0) == "$0.00000"


def test_analysis_returns_text_and_cost(monkeypatch) -> None:
    opener = _Opener(_answer("Суть: срыв поставки"))
    monkeypatch.setattr("urllib.request.build_opener", lambda *a, **k: opener)

    result = analyze_intake(INTAKE, api_key="sk-test")

    assert result.ok is True
    assert result.text == "Суть: срыв поставки"
    assert result.prompt_tokens == 100
    assert result.cost_usd > 0


def test_prompt_forbids_legal_advice() -> None:
    """Границы разбора заданы в промпте: оценки и советы — работа юриста."""
    assert "не давай правовых оценок" in SYSTEM_PROMPT
    assert "не советуй клиенту" in SYSTEM_PROMPT


def test_missing_key_does_not_raise(monkeypatch) -> None:
    result = analyze_intake(INTAKE, api_key="")

    assert result.ok is False
    assert result.error == "api_key_missing"


def test_network_failure_is_reported_not_raised(monkeypatch) -> None:
    """Недоступность вендора не должна ломать приём обращения."""

    class _Failing:
        def open(self, *a, **k):
            raise urllib.error.URLError("unreachable")

    monkeypatch.setattr("urllib.request.build_opener", lambda *a, **k: _Failing())

    result = analyze_intake(INTAKE, api_key="sk-test")

    assert result.ok is False
    assert result.text == ""


def test_api_error_is_reported_not_raised(monkeypatch) -> None:
    opener = _Opener({"error": {"message": "model not found"}})
    monkeypatch.setattr("urllib.request.build_opener", lambda *a, **k: opener)

    result = analyze_intake(INTAKE, api_key="sk-test")

    assert result.ok is False
    assert "model not found" in (result.error or "")


def test_proxy_is_used_when_configured(monkeypatch) -> None:
    """Вендор недоступен напрямую по региону — запрос идёт через прокси."""
    seen: dict[str, object] = {}

    def _fake_proxy_handler(mapping):
        seen["proxies"] = mapping
        return object()

    opener = _Opener(_answer())
    monkeypatch.setattr("urllib.request.ProxyHandler", _fake_proxy_handler)
    monkeypatch.setattr("urllib.request.build_opener", lambda *a, **k: opener)

    analyze_intake(INTAKE, api_key="sk-test", proxy_url="http://192.168.64.1:10811")

    assert seen["proxies"] == {
        "http": "http://192.168.64.1:10811",
        "https": "http://192.168.64.1:10811",
    }


def test_intake_fields_reach_the_model(monkeypatch) -> None:
    opener = _Opener(_answer())
    monkeypatch.setattr("urllib.request.build_opener", lambda *a, **k: opener)

    analyze_intake(
        {"description": "спор с подрядчиком", "region": "Москва", "deadline": "10 дней"},
        api_key="sk-test",
    )

    body = json.loads(opener.request.data.decode("utf-8"))
    user_message = body["messages"][1]["content"]

    assert "спор с подрядчиком" in user_message
    assert "Москва" in user_message
    assert "10 дней" in user_message
