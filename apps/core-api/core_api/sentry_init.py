"""Sentry: подключение и защита персональных данных перед отправкой.

Обращения содержат обстоятельства разводов, долгов, увольнений; договоры —
ФИО, контакты, суммы. Sentry — SaaS вне РФ, и трансграничная передача таких
данных требует осознанного решения, а не побочного эффекта включения
мониторинга. Поэтому здесь не «просто sentry_sdk.init()», а инициализация с
несколькими независимыми уровнями защиты:

1. send_default_pii=False — SDK не добавляет IP, cookies, заголовки запроса.
2. max_request_body_size="never" — тело запроса не попадает в событие вовсе.
   Это самый широкий рычаг: без него в событие могли бы попасть описание
   обращения, ФИО и суммы прямо из тела POST-запроса.
3. before_send — точечная зачистка полей, которые всё же могут доехать через
   extra/contexts (например, если где-то в коде добавили `extra={...}` с
   куском текста обращения). Список полей соответствует тому, что реально
   гуляет по этой платформе: description, subject, contact, price_text и т.п.

Уровни 1 и 2 — общий барьер, уровень 3 — страховка на случай, если код
когда-нибудь передаст чувствительное поле явно. Полагаться только на один из
них означало бы поставить конфиденциальность клиентов в зависимость от того,
не забыл ли кто-то одну настройку.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Ключи, которые не должны попасть в Sentry ни при каких обстоятельствах —
# независимо от того, где в структуре события они всплыли. Имена собраны по
# факту использования в моделях и схемах платформы, а не абстрактно.
_SENSITIVE_KEYS = frozenset(
    {
        "description",
        "internal_note",
        "subject",
        "scope_text",
        "exclusions_text",
        "schedule_text",
        "price_text",
        "payment_terms",
        "contact",
        "name",
        "signer_full_name",
        "signer_contact",
        "signer_org",
        "signer_name",
        "client_name",
        "client_contact",
        "client_org",
        "client_snapshot",
        "operator_snapshot",
        "answer_text",
        "question_text",
        "text",
        "document_text",
        "email",
        "phone",
        "company",
    }
)

_REDACTED = "[removed]"


def _scrub(value: object, *, depth: int = 0) -> object:
    """Рекурсивно вычищает чувствительные ключи из словарей/списков.

    Глубина ограничена: событие Sentry — не то место, где стоит гонять
    сложные вложенные структуры без предела, а глубже пяти уровней в этих
    данных содержательных полей уже не бывает.
    """
    if depth > 5:
        return value
    if isinstance(value, dict):
        return {
            key: (_REDACTED if key in _SENSITIVE_KEYS else _scrub(val, depth=depth + 1))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item, depth=depth + 1) for item in value]
    return value


def _before_send(event: dict, hint: dict) -> dict | None:
    _ = hint
    for section in ("extra", "contexts"):
        if section in event and isinstance(event[section], dict):
            event[section] = _scrub(event[section])
    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict) and isinstance(breadcrumbs.get("values"), list):
        for crumb in breadcrumbs["values"]:
            if isinstance(crumb, dict) and isinstance(crumb.get("data"), dict):
                crumb["data"] = _scrub(crumb["data"])
    request = event.get("request")
    if isinstance(request, dict):
        # Тело запроса и так не долетает (max_request_body_size="never"), но
        # заголовки могут нести Idempotency-Key и прочее — не персональные
        # данные, а рабочие идентификаторы, оставляем.
        request.pop("data", None)
    return event


def init_sentry() -> None:
    """Включает Sentry, если задан DSN. Без него — тихо не делает ничего.

    Сбой самой инициализации не должен ронять сервис: мониторинг — это
    удобство, а не условие работы core-api.
    """
    from core_api.config import get_settings

    settings = get_settings()
    dsn = getattr(settings, "sentry_dsn", None)
    if not dsn:
        logger.info("sentry_disabled", extra={"reason": "SENTRY_DSN not set"})
        return

    try:
        import sentry_sdk
    except ImportError:
        logger.warning("sentry_disabled", extra={"reason": "sentry-sdk not installed"})
        return

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=settings.environment,
            send_default_pii=False,
            max_request_body_size="never",
            include_local_variables=False,
            before_send=_before_send,
            # Разбор ошибок здесь важнее задержек запросов — трассировку
            # производительности не включаем, это отдельное решение с своей
            # ценой (объём событий, ещё один канал для утечки данных из
            # параметров запроса).
            traces_sample_rate=0.0,
        )
        logger.info("sentry_initialized", extra={"environment": settings.environment})
    except Exception as error:  # noqa: BLE001 — инициализация не критична
        logger.warning("sentry_init_failed", extra={"error": type(error).__name__})
