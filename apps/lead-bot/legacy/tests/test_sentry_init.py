"""Защита персональных данных перед отправкой в Sentry — сторона бота.

Через этот процесс проходят обстоятельства обращений раньше, чем они попадают
в ядро. Проверяется то же, что и на стороне core-api: чувствительные поля не
долетают до события, а сама интеграция не включается без явного DSN.
"""

from __future__ import annotations

from types import SimpleNamespace

from sentry_init import _SENSITIVE_KEYS, _before_send, _scrub, init_sentry


def test_sensitive_fields_are_redacted() -> None:
    scrubbed = _scrub(
        {
            "description": "Уволили без объяснения причин",
            "signer_contact": "+79000000000",
            "username": "ryabov",
            "status": "new",
        }
    )
    assert scrubbed["description"] == "[removed]"
    assert scrubbed["signer_contact"] == "[removed]"
    assert scrubbed["username"] == "[removed]"
    assert scrubbed["status"] == "new"


def test_before_send_scrubs_extra_and_breadcrumbs() -> None:
    event = {
        "extra": {"pain_point": "чувствительно"},
        "breadcrumbs": {"values": [{"data": {"contact": "@ivanov"}}]},
    }
    result = _before_send(event, {})
    assert result["extra"]["pain_point"] == "[removed]"
    assert result["breadcrumbs"]["values"][0]["data"]["contact"] == "[removed]"


def test_no_dsn_means_no_init(monkeypatch) -> None:
    """Мониторинг включается явным заданием DSN, а не молчаливым переходом
    в SaaS вне РФ по умолчанию."""
    import sentry_sdk

    called = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: called.append(kwargs))
    init_sentry(SimpleNamespace(SENTRY_DSN="", ENVIRONMENT="production"))
    assert called == []


def test_dsn_present_enables_with_safe_defaults(monkeypatch) -> None:
    import sentry_sdk

    captured = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: captured.update(kwargs))
    init_sentry(SimpleNamespace(SENTRY_DSN="https://key@example.ingest.sentry.io/1", ENVIRONMENT="production"))

    assert captured["send_default_pii"] is False
    assert captured["max_request_body_size"] == "never"
    assert captured["include_local_variables"] is False
    assert captured["before_send"] is _before_send


def test_all_known_sensitive_fields_covered() -> None:
    required = {"description", "pain_point", "signer_contact", "contact", "username"}
    assert required <= _SENSITIVE_KEYS
