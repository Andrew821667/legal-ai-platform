"""Отправка из ядра в Telegram — с журналом, повторами и проверкой связи.

Ядро месяцами отправляло договоры, акты, ответы клиентам и уведомления о
лидах без прокси. Всё это падало в лог, и юрист узнал о сбое, только нажав
«Отправить» и получив «ядро не ответило». Здесь три вещи:

- журнал: у каждой отправки есть исход, и он пишется отдельной транзакцией —
  запрос, упавший с 502, не должен утащить за собой и запись о сбое;
- повторы: фоновые уведомления при сбое повторяются с растущей паузой;
  договор, ответ клиенту и акт — нет: юрист видит ошибку сразу, а повтор без
  него прислал бы клиенту то, что он, возможно, уже отправил заново;
- связь: ядро регулярно проверяет, достаёт ли оно до Telegram, и если нет
  дольше нескольких минут — говорит владельцу через бота, у которого своя
  дорога в Telegram.

Запускает проверку и повторы бот: у ядра нет своего планировщика, а у бота
уже крутятся периодические задачи (см. telegram_tick_job).
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import select

from core_api.client_notices import queue_notice
from core_api.config import get_settings, telegram_proxies
from core_api.db import SessionLocal
from core_api.models import ServiceHealth, TelegramDelivery

logger = logging.getLogger(__name__)

# Паузы перед повторами, минуты: от минуты до восьми часов — около суток.
RETRY_MINUTES = (1, 5, 15, 30, 60, 120, 240, 480)
MAX_ATTEMPTS = len(RETRY_MINUTES) + 1
# Сколько ждать повтора, прежде чем показать отправку в «Не доставлено».
STUCK_AFTER = timedelta(minutes=10)
# Сколько терпеть отсутствие связи, прежде чем сказать владельцу.
ALERT_AFTER = timedelta(minutes=10)
# Сколько держать отправку за тем, кто её взял на повтор.
_LEASE = timedelta(minutes=10)
HEALTH_KEY = "telegram_core"

KIND_LABELS = {
    "lead_notice": "Уведомление о новом лиде",
    "intake_notice": "Уведомление о новом обращении",
    "agreement": "Договор клиенту",
    "agreement_reply": "Ответ клиенту",
    "work_act": "Акт клиенту",
    "act_reminder": "Напоминание об оплате",
    "agreement_reminder": "Напоминание о договоре",
}

_TOKEN = re.compile(r"bot\d+:[A-Za-z0-9_-]+")

Transport = Callable[..., dict]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def safe_error(exc: BaseException) -> str:
    """Текст ошибки без токена бота: requests кладёт в сообщение адрес с ним."""
    return _TOKEN.sub("bot<token>", f"{type(exc).__name__}: {exc}")[:500]


def _default_transport() -> Transport:
    from core_api.lead_notifications import _post_telegram_message

    return _post_telegram_message


def _notify_token() -> str:
    return get_settings().lead_notify_bot_token or ""


def _client_token() -> str:
    settings = get_settings()
    return getattr(settings, "lead_bot_token", None) or settings.lead_notify_bot_token or ""


def _extras(reply_markup: str | None, parse_mode: str | None) -> dict:
    """Только заданные параметры: у транспорта они необязательные."""
    extras: dict = {}
    if reply_markup is not None:
        extras["reply_markup"] = reply_markup
    if parse_mode is not None:
        extras["parse_mode"] = parse_mode
    return extras


def _record_failure(row: TelegramDelivery, exc: BaseException, now: datetime) -> None:
    row.attempts += 1
    row.last_error = safe_error(exc)
    if row.retryable and row.attempts < MAX_ATTEMPTS:
        row.status = "pending"
        row.next_attempt_at = now + timedelta(minutes=RETRY_MINUTES[row.attempts - 1])
    else:
        row.status = "failed"
        row.next_attempt_at = None


def _record_success(row: TelegramDelivery, result: dict, now: datetime) -> None:
    row.attempts += 1
    row.status = "sent"
    row.sent_at = now
    row.next_attempt_at = None
    row.last_error = None
    message_id = result.get("message_id") if isinstance(result, dict) else None
    row.message_id = int(message_id) if isinstance(message_id, int) else None


def send(
    *,
    kind: str,
    token: str,
    chat_id: str | int,
    text: str,
    reply_markup: str | None = None,
    parse_mode: str | None = None,
    retryable: bool = False,
    lead_id: uuid.UUID | None = None,
    agreement_id: uuid.UUID | None = None,
    act_id: uuid.UUID | None = None,
    transport: Transport | None = None,
) -> dict:
    """Отправляет сейчас и записывает исход. При неудаче — бросает исключение
    транспорта, но уже после записи: вызывающий решает, что сказать юристу."""
    transport = transport or _default_transport()
    db = SessionLocal()
    try:
        row = TelegramDelivery(
            kind=kind,
            chat_id=str(chat_id),
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            status="pending",
            retryable=retryable,
            attempts=0,
            lead_id=lead_id,
            agreement_id=agreement_id,
            act_id=act_id,
        )
        db.add(row)
        db.commit()
        try:
            result = transport(token, str(chat_id), text, **_extras(reply_markup, parse_mode))
        except Exception as exc:
            _record_failure(row, exc, _now())
            db.commit()
            raise
        _record_success(row, result, _now())
        db.commit()
        return result
    finally:
        db.close()


def _attempt(delivery_id: uuid.UUID, transport: Transport) -> str:
    """Повторная попытка одной отправки — в своей транзакции."""
    db = SessionLocal()
    try:
        row = db.get(TelegramDelivery, delivery_id)
        if row is None or row.status == "sent":
            return "sent" if row else "missing"
        token = _notify_token()
        if not token:
            return row.status
        try:
            result = transport(token, row.chat_id, row.text, **_extras(row.reply_markup, row.parse_mode))
        except Exception as exc:  # noqa: BLE001 — исход пишется в журнал
            _record_failure(row, exc, _now())
        else:
            _record_success(row, result, _now())
        db.commit()
        return row.status
    finally:
        db.close()


def process_due(limit: int = 20, transport: Transport | None = None) -> dict:
    """Повторяет фоновые отправки, чей срок подошёл.

    Сначала берёт их в аренду и отпускает блокировку: одна попытка может
    длиться до минуты, держать строки заблокированными всё это время незачем.
    """
    transport = transport or _default_transport()
    now = _now()
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(TelegramDelivery)
            .where(
                TelegramDelivery.status == "pending",
                TelegramDelivery.retryable.is_(True),
                TelegramDelivery.dismissed_at.is_(None),
                TelegramDelivery.next_attempt_at <= now,
            )
            .order_by(TelegramDelivery.next_attempt_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        ).all()
        ids = [row.id for row in rows]
        for row in rows:
            row.next_attempt_at = now + _LEASE
        db.commit()
    finally:
        db.close()
    outcome = {"sent": 0, "pending": 0, "failed": 0}
    for delivery_id in ids:
        status = _attempt(delivery_id, transport)
        if status in outcome:
            outcome[status] += 1
    return outcome


def retry_now(delivery_id: uuid.UUID, transport: Transport | None = None) -> str:
    """Юрист нажал «Повторить». Только для фоновых уведомлений — см. модуль."""
    db = SessionLocal()
    try:
        row = db.get(TelegramDelivery, delivery_id)
        if row is None:
            return "missing"
        if not row.retryable:
            return "not_retryable"
        if row.status == "failed":
            # Новая серия попыток: исчерпанный счётчик не должен мешать ручному повтору.
            row.attempts = 0
            row.status = "pending"
            db.commit()
    finally:
        db.close()
    return _attempt(delivery_id, transport or _default_transport())


def check_health(http_get: Callable[..., requests.Response] | None = None) -> dict:
    """Достаёт ли ядро до Telegram своей дорогой — тем же токеном и прокси.

    Молчать о сбое дольше ALERT_AFTER нельзя: сообщение владельцу уходит через
    очередь уведомлений, её доставляет бот — у него свой путь в Telegram.
    """
    token = _client_token()
    if not token:
        return {"ok": None, "skipped": "no_token"}
    http_get = http_get or requests.get
    now = _now()
    error: str | None = None
    try:
        response = http_get(
            f"https://api.telegram.org/bot{token}/getMe", timeout=10, proxies=telegram_proxies()
        )
        response.raise_for_status()
        ok = bool(response.json().get("ok"))
        if not ok:
            error = "Telegram ответил ok=false"
    except Exception as exc:  # noqa: BLE001 — сбой и есть результат проверки
        ok = False
        error = safe_error(exc)

    db = SessionLocal()
    try:
        row = db.get(ServiceHealth, HEALTH_KEY, with_for_update=True)
        if row is None:
            row = ServiceHealth(key=HEALTH_KEY, ok=True)
            db.add(row)
        row.checked_at = now
        if ok:
            if row.alerted_at is not None and row.failing_since is not None:
                queue_notice(
                    db,
                    f"telegram_up:{row.failing_since.isoformat()}",
                    "Связь ядра с Telegram восстановлена. Неотправленные уведомления уйдут "
                    "сами; договоры, ответы и акты из «Не доставлено» отправьте заново.",
                )
            row.ok = True
            row.failing_since = None
            row.alerted_at = None
            row.last_error = None
        else:
            row.ok = False
            row.failing_since = row.failing_since or now
            row.last_error = error
            if row.alerted_at is None and now - row.failing_since >= ALERT_AFTER:
                since = row.failing_since.astimezone(timezone(timedelta(hours=3))).strftime("%H:%M")
                queue_notice(
                    db,
                    f"telegram_down:{row.failing_since.isoformat()}",
                    f"Ядро не достаёт до Telegram с {since} МСК. Договоры, акты и ответы "
                    f"клиентам из рабочего места не уходят. Проверьте прокси. Ошибка: {error}",
                )
                row.alerted_at = now
        db.commit()
        return {
            "ok": row.ok,
            "failing_since": row.failing_since.isoformat() if row.failing_since else None,
            "error": row.last_error,
        }
    finally:
        db.close()


def tick() -> dict:
    """Проверка связи и повторы — то, что бот запускает раз в пару минут.

    Без связи повторы не гоняются: иначе долгий сбой прокси сжёг бы все
    попытки впустую, и уведомления упали бы в «не доставлено», хотя связь
    вот-вот вернётся.
    """
    health = check_health()
    due = process_due() if health.get("ok") else {"skipped": True}
    return {"health": health, "due": due}


def health_snapshot(db) -> dict | None:
    row = db.get(ServiceHealth, HEALTH_KEY)
    if row is None:
        return None
    return {
        "ok": row.ok,
        "checked_at": row.checked_at.isoformat() if row.checked_at else None,
        "failing_since": row.failing_since.isoformat() if row.failing_since else None,
        "last_error": row.last_error,
    }
