"""Проверки выбора прокси для reader-бота.

Прямой доступ к api.telegram.org с production-хоста закрыт. Раньше бот
создавался как Bot(token=token) без сессии и падал с ClientConnectorError на
каждом обращении — он не работал вовсе, независимо от состояния канала.

Тест намеренно проверяет чистую функцию, а не сборку Bot: aiogram живёт в
окружении legacy-образа, и тест с его импортом просто пропускался бы в CI.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE = (
    Path(__file__).resolve().parents[1]
    / "legacy"
    / "app"
    / "telegram_session.py"
)
_spec = importlib.util.spec_from_file_location("reader_telegram_session", MODULE)
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
resolve_proxy_url = _module.resolve_proxy_url


def test_configured_proxy_is_used() -> None:
    assert resolve_proxy_url("http://192.168.64.1:10811") == "http://192.168.64.1:10811"


def test_missing_proxy_keeps_direct_mode() -> None:
    """Без прокси поведение прежнее — важно для локального запуска."""
    assert resolve_proxy_url(None) is None
    assert resolve_proxy_url("") is None


def test_blank_value_is_not_treated_as_address() -> None:
    """Объявленная, но незаполненная переменная не должна ломать сессию."""
    assert resolve_proxy_url("   ") is None


def test_surrounding_spaces_are_trimmed() -> None:
    assert resolve_proxy_url("  http://192.168.64.1:10811  ") == "http://192.168.64.1:10811"
