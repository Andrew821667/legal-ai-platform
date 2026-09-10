"""Sentry для лид-бота: та же защита данных, что и в core-api, своя версия.

Через этот процесс проходят обстоятельства обращений — описания разводов,
долгов, увольнений — раньше, чем они попадают в ядро. Уровни защиты те же три,
что в core_api/sentry_init.py: без PII, без тела запроса (здесь это тело
Telegram-апдейта — оно тоже несёт текст сообщения клиента), точечная зачистка
как страховка. Модуль не переиспользует core_api/sentry_init.py напрямую: это
два разных процесса без общего пакета, и держать код продублированным явно
дешевле, чем городить общую зависимость ради одного файла.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = frozenset(
    {
        "description",
        "internal_note",
        "pain_point",
        "subject",
        "price_text",
        "payment_terms",
        "contact",
        "name",
        "first_name",
        "last_name",
        "username",
        "signer_full_name",
        "signer_contact",
        "signer_org",
        "answer_text",
        "text",
        "email",
        "phone",
        "company",
    }
)

_REDACTED = "[removed]"


def _scrub(value: object, *, depth: int = 0) -> object:
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
    return event


def init_sentry(config) -> None:
    """Включает Sentry, если задан SENTRY_DSN. Сбой инициализации не роняет бота."""
    dsn = getattr(config, "SENTRY_DSN", "")
    if not dsn:
        logger.info("Sentry не включён: SENTRY_DSN не задан")
        return

    try:
        import sentry_sdk
    except ImportError:
        logger.warning("Sentry не включён: пакет sentry-sdk не установлен")
        return

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=getattr(config, "ENVIRONMENT", "production"),
            send_default_pii=False,
            max_request_body_size="never",
            include_local_variables=False,
            before_send=_before_send,
            # Ошибки здесь редкие и штучные — трассировка производительности
            # не нужна, а лишний канал для утечки параметров запроса не нужен
            # тем более.
            traces_sample_rate=0.0,
        )
        logger.info("Sentry включён (%s)", getattr(config, "ENVIRONMENT", "production"))
    except Exception as error:  # noqa: BLE001 — инициализация не критична
        logger.warning("Sentry: сбой инициализации: %s", type(error).__name__)
