"""Что от лидов осталось в SQLite бота.

Сами лиды живут в ядре (см. core_leads). Здесь — только чтение старых строк
для одноразового переноса, отметка о переносе и журнал уведомлений
владельцу, который ссылается на номер лида.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)


def list_local_leads(get_connection: Callable[[], sqlite3.Connection]) -> list[dict]:
    """Все строки старой таблицы — для переноса в ядро."""
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute("SELECT * FROM leads ORDER BY id").fetchall()]
    finally:
        conn.close()


def set_core_lead_id(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    lead_id: int,
    core_lead_id: str,
) -> None:
    """Отметка «перенесён»: строка с core_lead_id при следующем старте пропускается."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE leads SET core_lead_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (core_lead_id, lead_id),
        )
        conn.commit()
    except Exception as error:
        logger.error("Error setting core_lead_id for lead %s: %s", lead_id, error)
        conn.rollback()
        raise
    finally:
        conn.close()


def create_notification(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    lead_id: int,
    notification_type: str,
    message: str,
) -> int:
    """Create an admin notification row."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO admin_notifications (lead_id, notification_type, message)
            VALUES (?, ?, ?)
            """,
            (lead_id, notification_type, message),
        )
        conn.commit()
        notification_id = cursor.lastrowid
        logger.info("Notification %s created for lead %s", notification_id, lead_id)
        return notification_id
    except Exception as error:
        logger.error("Error creating notification: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()
