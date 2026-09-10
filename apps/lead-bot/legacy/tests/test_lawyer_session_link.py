"""Ссылка для автономного входа в рабочее место — минуя Telegram.

Формат токена (id.issuedAt.hex-подпись) и алгоритм подписи (HMAC-SHA256)
должны совпадать с тем, что проверяет apps/web/lib/lawyer-session-token.ts —
это одна схема на двух языках. Здесь проверяется контракт формата и то, что
без секрета ссылка не выдаётся вовсе: выдать неподписываемую ссылку хуже, чем
не выдать её.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from lawyer_session_link import build_login_url, mint_session_token


def test_token_has_three_dot_separated_parts() -> None:
    token = mint_session_token(848510279, "secret")
    parts = token.split(".")
    assert len(parts) == 3
    assert parts[0] == "848510279"
    assert parts[1].isdigit()
    assert len(parts[2]) == 64  # hex sha256


def test_signature_matches_hmac_sha256_of_id_and_time() -> None:
    """Контракт формата: то же вычисление, что и на стороне веба
    (createHmac('sha256', secret).update(`${id}.${issuedAt}`).digest('hex'))."""
    token = mint_session_token(1, "shared-secret")
    user_id, issued_at, signature = token.split(".")
    expected = hmac.new(
        b"shared-secret", f"{user_id}.{issued_at}".encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert signature == expected


def test_different_secrets_produce_different_signatures() -> None:
    token_a = mint_session_token(1, "secret-a")
    token_b = mint_session_token(1, "secret-b")
    assert token_a.split(".")[2] != token_b.split(".")[2]


def test_token_carries_the_current_time() -> None:
    before = int(time.time())
    token = mint_session_token(1, "secret")
    after = int(time.time())
    issued_at = int(token.split(".")[1])
    assert before <= issued_at <= after


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
