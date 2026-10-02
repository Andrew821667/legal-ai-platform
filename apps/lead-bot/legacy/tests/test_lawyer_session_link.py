"""Одноразовая ссылка для автономного входа в рабочее место — минуя Telegram.

Формат токена (v2.id.issuedAt.ttl.nonce.hex-подпись) и подпись (HMAC-SHA256
над "lawyer-login.<id>.<issuedAt>.<ttl>.<nonce>") должны совпадать с тем, что
проверяет apps/web/lib/lawyer-login-token.ts — одна схема на двух языках.
Здесь проверяется контракт формата, случайность nonce (ссылка гасится по
нему) и то, что без секрета ссылка не выдаётся вовсе.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from lawyer_session_link import KEYBOARD_LINK_TTL_SECONDS, SAFARI_LINK_TTL_SECONDS, build_login_url, mint_login_token


def test_token_format_matches_the_site() -> None:
    before = int(time.time())
    token = mint_login_token(848510279, "shared-secret", ttl_seconds=900)
    after = int(time.time())
    version, user_id, issued_at, ttl, nonce, signature = token.split(".")
    assert (version, user_id, ttl) == ("v2", "848510279", "900")
    assert before <= int(issued_at) <= after
    assert len(nonce) == 32 and int(nonce, 16) >= 0
    expected = hmac.new(
        b"shared-secret", f"lawyer-login.{user_id}.{issued_at}.{ttl}.{nonce}".encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert signature == expected


def test_every_link_has_its_own_nonce() -> None:
    """Ссылка гасится по nonce: две ссылки подряд не должны совпасть."""
    first = mint_login_token(1, "secret", ttl_seconds=900).split(".")[4]
    second = mint_login_token(1, "secret", ttl_seconds=900).split(".")[4]
    assert first != second


def test_safari_link_is_short_and_keyboard_link_lives_until_next_admin() -> None:
    assert SAFARI_LINK_TTL_SECONDS == 15 * 60
    # Сайт не примет срок длиннее недели (LOGIN_TOKEN_MAX_TTL_SECONDS).
    assert KEYBOARD_LINK_TTL_SECONDS <= 7 * 24 * 60 * 60
    url = build_login_url(1, workspace_url="https://ai-verdict.ru/lawyer", secret="x")
    assert url.split("token=")[1].split(".")[3] == str(SAFARI_LINK_TTL_SECONDS)


def test_no_link_without_secret() -> None:
    """Выдать ссылку, которую сервер не сможет проверить, хуже её отсутствия."""
    assert build_login_url(1, workspace_url="https://ai-verdict.ru/lawyer", secret="") is None


def test_no_link_without_workspace_url() -> None:
    assert build_login_url(1, workspace_url="", secret="x") is None


def test_login_url_points_at_the_login_route_not_the_workspace_itself() -> None:
    url = build_login_url(1, workspace_url="https://ai-verdict.ru/lawyer", secret="x")
    assert url.startswith("https://ai-verdict.ru/lawyer/login?token=")
    # /lawyer/lawyer/login была бы результатом наивной склейки без отреза хвоста.
    assert "/lawyer/lawyer/" not in url


def test_login_url_survives_a_trailing_slash() -> None:
    url = build_login_url(1, workspace_url="https://ai-verdict.ru/lawyer/", secret="x")
    assert url.startswith("https://ai-verdict.ru/lawyer/login?token=")
