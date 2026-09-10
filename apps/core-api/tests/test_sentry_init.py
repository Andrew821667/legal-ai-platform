"""Защита персональных данных перед отправкой в Sentry.

Sentry — SaaS вне РФ, и в этой платформе через него могли бы утечь описания
обращений, ФИО и суммы договоров. Проверяется именно это: чувствительные поля
не долетают до события ни при каких обстоятельствах, а сама интеграция не
включается без явно заданного DSN.
"""

from __future__ import annotations

from core_api.sentry_init import _SENSITIVE_KEYS, _before_send, _scrub, init_sentry


def test_sensitive_fields_are_redacted() -> None:
    scrubbed = _scrub(
        {
            "description": "Раздел совместно нажитого имущества, квартира в ипотеке",
            "signer_full_name": "Рябов Александр Алексеевич",
            "signer_contact": "+79000000000",
            "price_text": "80 000 ₽",
            "status": "draft",  # не персональные данные — остаётся как есть
        }
    )
    assert scrubbed["description"] == "[removed]"
    assert scrubbed["signer_full_name"] == "[removed]"
    assert scrubbed["signer_contact"] == "[removed]"
    assert scrubbed["price_text"] == "[removed]"
    assert scrubbed["status"] == "draft"


def test_scrub_reaches_nested_structures() -> None:
    """client_snapshot и подобные словари сами по себе тоже вычищаются целиком —
    вложенные в них поля могут быть чем угодно, и разбирать их по одной незачем."""
    scrubbed = _scrub({"agreement": {"client_snapshot": {"full_name": "Иванов"}}})
    assert scrubbed["agreement"]["client_snapshot"] == "[removed]"


def test_scrub_walks_lists() -> None:
    scrubbed = _scrub([{"description": "текст"}, {"status": "ok"}])
    assert scrubbed[0]["description"] == "[removed]"
    assert scrubbed[1]["status"] == "ok"


def test_scrub_does_not_recurse_forever() -> None:
    """Глубина ограничена — не должно уйти в бесконечность на самодельной структуре."""
    deep = {"a": {}}
    node = deep["a"]
    for _ in range(20):
        node["a"] = {"description": "утечёт, если разбор не остановится"}
        node = node["a"]
    result = _scrub(deep)
    assert result is not None  # не упало


def test_before_send_scrubs_extra_and_contexts() -> None:
    event = {
        "extra": {"description": "чувствительно"},
        "contexts": {"agreement": {"price_text": "10 000 ₽"}},
    }
    result = _before_send(event, {})
    assert result["extra"]["description"] == "[removed]"
    assert result["contexts"]["agreement"]["price_text"] == "[removed]"


def test_before_send_drops_request_body() -> None:
    """Страховка поверх max_request_body_size='never': тело не должно остаться,
    даже если до before_send событие дошло с ним."""
    event = {"request": {"method": "POST", "url": "/api/v1/service-agreements", "data": {"subject": "x"}}}
    result = _before_send(event, {})
    assert "data" not in result["request"]
    assert result["request"]["method"] == "POST"


def test_before_send_scrubs_breadcrumbs() -> None:
    event = {
        "breadcrumbs": {
            "values": [{"data": {"contact": "@ivanov"}}, {"message": "no data field"}]
        }
    }
    result = _before_send(event, {})
    assert result["breadcrumbs"]["values"][0]["data"]["contact"] == "[removed]"


def test_no_dsn_means_no_init(monkeypatch) -> None:
    """Мониторинг включается явным заданием DSN, а не молчаливым переходом
    в SaaS вне РФ по умолчанию."""
    import core_api.config as config_module

    monkeypatch.setattr(config_module.get_settings(), "sentry_dsn", None, raising=False)
    # sentry_sdk.init не должен быть вызван вовсе.
    import sentry_sdk

    called = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: called.append(kwargs))
    init_sentry()
    assert called == []


def test_dsn_present_enables_with_safe_defaults(monkeypatch) -> None:
    import core_api.config as config_module
    import sentry_sdk

    monkeypatch.setattr(
        config_module.get_settings(), "sentry_dsn", "https://key@example.ingest.sentry.io/1", raising=False
    )
    captured = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: captured.update(kwargs))
    init_sentry()

    assert captured["send_default_pii"] is False
    assert captured["max_request_body_size"] == "never"
    assert captured["include_local_variables"] is False
    assert captured["before_send"] is _before_send
    assert captured["traces_sample_rate"] == 0.0


def test_all_known_sensitive_fields_covered() -> None:
    """Список не пуст и содержит хотя бы обязательные поля, которые точно
    встречаются в моделях платформы — если кто-то случайно урежет список,
    тест должен упасть."""
    required = {"description", "signer_full_name", "signer_contact", "price_text", "contact"}
    assert required <= _SENSITIVE_KEYS
