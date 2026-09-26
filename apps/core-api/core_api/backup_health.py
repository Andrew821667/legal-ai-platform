"""Свежесть бэкапа базы — чтобы о пропавшем бэкапе узнать сразу, а не при аварии.

Бэкап делает не ядро, а ночная задача на Mac mini (infra/scripts/backup_postgres.sh):
она пишет итог в service_health под ключом backup — когда был последний
удачный дамп и удалась ли копия на NAS. Ядро в своём такте смотрит сюда:
дампа нет больше суток или копия не удалась — одно сообщение владельцу через
очередь уведомлений (её доставляет бот). Следующий удачный бэкап сбрасывает
отметку, и о новом сбое снова скажем.

Строки нет вовсе — бэкап на этой машине не настроен, молчим.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core_api.client_notices import queue_notice
from core_api.db import SessionLocal
from core_api.models import ServiceHealth

KEY = "backup"
# Бэкап ночью раз в сутки: 26 часов — с запасом на задержку запуска.
STALE_AFTER = timedelta(hours=26)
_MSK = timezone(timedelta(hours=3))


def _msk(value: datetime | None) -> str:
    return value.astimezone(_MSK).strftime("%d.%m %H:%M") if value else "—"


def problem(row: ServiceHealth, now: datetime) -> tuple[str, str] | None:
    """(вид, текст) проблемы с бэкапом или None."""
    if row.checked_at is None or now - row.checked_at > STALE_AFTER:
        return "stale", f"Бэкап базы не делался больше суток: последний удачный — {_msk(row.checked_at)} МСК."
    if not row.ok:
        return "error", f"Бэкап базы {_msk(row.checked_at)} МСК: {row.last_error or 'сбой'}."
    return None


def check(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        row = db.get(ServiceHealth, KEY, with_for_update=True)
        if row is None:
            return {"skipped": "not_configured"}
        found = problem(row, now)
        if found and row.alerted_at is None:
            kind, text = found
            marker = (row.checked_at or now).isoformat()
            queue_notice(
                db,
                f"backup:{kind}:{marker}",
                f"{text}\nПроверьте на Mac mini: sudo launchctl print system/ru.legalai.postgres-backup "
                "и ~/backups/legal-ai/backup.log (пользователь andrej).",
            )
            row.alerted_at = now
        db.commit()
        return {"ok": found is None, "last": row.checked_at.isoformat() if row.checked_at else None}
    finally:
        db.close()


def digest_line(db, now: datetime) -> str | None:
    """Строка для сводки за неделю."""
    row = db.get(ServiceHealth, KEY)
    if row is None:
        return None
    found = problem(row, now)
    if found:
        return f"⚠️ {found[1]}"
    return f"Бэкап базы: последний {_msk(row.checked_at)} МСК, всё в порядке."
