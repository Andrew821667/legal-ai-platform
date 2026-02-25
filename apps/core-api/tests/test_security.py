from __future__ import annotations

import pytest
from fastapi import HTTPException

from core_api.auth import ApiKeyIdentity, require_scopes
from core_api.models import Scope
from core_api.security import generate_api_key, hash_api_key, verify_api_key


def test_generate_and_verify_api_key() -> None:
    key = generate_api_key()
    assert key.startswith("ak_")
    key_hash = hash_api_key(key)
    assert verify_api_key(key, key_hash)


def test_scope_enforcement_blocks_wrong_scope() -> None:
    dependency = require_scopes(Scope.bot)
    identity = ApiKeyIdentity(id=__import__("uuid").uuid4(), scope=Scope.news, name="news")

    with pytest.raises(HTTPException) as exc:
        dependency(identity=identity)

    assert exc.value.status_code == 403
