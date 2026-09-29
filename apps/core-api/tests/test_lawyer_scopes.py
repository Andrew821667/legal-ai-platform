"""Рабочее место юриста — только ключ администратора.

Ключ бота есть у сайта, лид-бота и ассистента; раньше он же открывал список
клиентов, карточки, документы и деньги. Бот этими эндпоинтами не пользуется.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from core_api.main import app
from core_api.models import Scope
from fastapi.testclient import TestClient

from test_practice import _cleanup, _key

PATHS = [
    "/api/v1/lawyer/today",
    "/api/v1/lawyer/clients",
    f"/api/v1/lawyer/clients/{uuid4()}",
    "/api/v1/lawyer/finance",
    "/api/v1/lawyer/funnel",
    "/api/v1/lawyer/archive",
    f"/api/v1/lawyer/documents/{uuid4()}",
]


@pytest.mark.parametrize("path", PATHS)
def test_bot_key_cannot_read_the_lawyer_workspace(path) -> None:
    names = [f"pytest.scopes.bot.{uuid4().hex}", f"pytest.scopes.admin.{uuid4().hex}"]
    client = TestClient(app)
    try:
        assert client.get(path, headers={"X-API-Key": _key(Scope.bot, names[0])}).status_code == 403
        # Администратору путь по-прежнему доступен (или честное 404 для чужого id).
        assert client.get(path, headers={"X-API-Key": _key(Scope.admin, names[1])}).status_code in (200, 404)
    finally:
        _cleanup(names, None)
