"""Журнал удалений — триггером в базе, мимо кода приложения.

Обращение клиента исчезло из базы без единой записи в аудите: код приложения
удаляет обращения только вместе с клиентом («Удалить навсегда»), а клиент
остался. Значит, строку удалили в обход кода. Триггер в самой базе ловит
любое удаление — из ядра, из psql, из скрипта — и пишет, что, когда и кем.

Только что и кем, без содержимого строки: «Удалить навсегда» обязано
действительно стирать персональные данные, и копия удалённого в журнале
делала бы удаление фикцией.
"""

from __future__ import annotations

# Таблицы, удаление из которых теряет дело клиента.
WATCHED_TABLES = (
    "leads",
    "legal_intakes",
    "service_agreements",
    "work_acts",
    "nda_signatures",
    "intake_documents",
)

FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION log_deletion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    old_row jsonb := to_jsonb(OLD);
BEGIN
    INSERT INTO deletion_log (table_name, row_id, lead_id)
    VALUES (TG_TABLE_NAME, old_row->>'id', old_row->>'lead_id');
    RETURN OLD;
END
$$;
"""


def trigger_sql(table: str) -> list[str]:
    return [
        f"DROP TRIGGER IF EXISTS trg_log_deletion ON {table}",
        f"CREATE TRIGGER trg_log_deletion AFTER DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION log_deletion()",
    ]


def all_statements() -> list[str]:
    statements = [FUNCTION_SQL]
    for table in WATCHED_TABLES:
        statements += trigger_sql(table)
    return statements


# Так представляется ядро (core_api/db.py): его удаления — штатные.
APP_NAME = "legal-ai-core-api"
_LABELS = {
    "leads": "клиенты",
    "legal_intakes": "обращения",
    "service_agreements": "договоры",
    "work_acts": "акты",
    "nda_signatures": "подписи NDA",
    "intake_documents": "документы по делам",
}


def watch(now=None) -> dict:
    """Удаления мимо приложения за сутки — владельцу, по одному сообщению на транзакцию.

    Штатные удаления («Удалить навсегда», чистка) идут от ядра и не тревожат.
    Повтор такта не дублирует: ключ уведомления — номер транзакции.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, or_, select

    from core_api.client_notices import queue_notice
    from core_api.db import SessionLocal
    from core_api.models import DeletionLog

    now = now or datetime.now(timezone.utc)
    msk = timezone(timedelta(hours=3))
    db = SessionLocal()
    try:
        rows = db.execute(
            select(
                DeletionLog.txid,
                DeletionLog.table_name,
                func.count(),
                func.min(DeletionLog.deleted_at),
                func.max(DeletionLog.db_user),
                func.max(DeletionLog.application_name),
            )
            .where(DeletionLog.deleted_at >= now - timedelta(days=1))
            .where(or_(DeletionLog.application_name.is_(None), DeletionLog.application_name != APP_NAME))
            .group_by(DeletionLog.txid, DeletionLog.table_name)
        ).all()
        by_tx: dict = {}
        for txid, table, count, at, user, app in rows:
            entry = by_tx.setdefault(txid, {"parts": [], "at": at, "user": user, "app": app})
            entry["parts"].append(f"{_LABELS.get(table, table)} — {count}")
            entry["at"] = min(entry["at"], at)
        for txid, entry in by_tx.items():
            queue_notice(
                db,
                f"deletion:{txid}",
                "В базе удалены записи мимо приложения: "
                + ", ".join(entry["parts"])
                + f". Кто: пользователь БД {entry['user']}, программа {entry['app'] or 'не указана'}, "
                + f"{entry['at'].astimezone(msk):%d.%m %H:%M} МСК. Если это не вы — проверьте, у кого доступ к базе.",
            )
        db.commit()
        return {"transactions": len(by_tx)}
    finally:
        db.close()
