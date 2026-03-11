"""
Conversation history helpers extracted from the legacy Database class.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)


def add_message(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    user_id: int,
    role: str,
    message: str,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO conversations (user_id, role, message)
            VALUES (?, ?, ?)
            """,
            (user_id, role, message),
        )
        conn.commit()
        logger.debug("Message added for user %s, role %s", user_id, role)
    except Exception as error:
        logger.error("Error adding message: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def get_conversation_history(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    user_id: int,
    limit: int,
) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT role, message, timestamp
            FROM conversations
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        conn.close()


def clear_conversation_history(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    user_id: int,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        conn.commit()
        logger.info("Conversation history cleared for user %s", user_id)
    except Exception as error:
        logger.error("Error clearing conversation: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def cleanup_conversations_by_retention(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    retention_days: int,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            DELETE FROM conversations
            WHERE timestamp < datetime('now', ?)
            """,
            (f"-{retention_days} days",),
        )
        deleted = cursor.rowcount
        conn.commit()
        if deleted:
            logger.info(
                "Conversation retention cleanup deleted %s messages older than %s days",
                deleted,
                retention_days,
            )
        return deleted
    except Exception as error:
        logger.error("Error cleaning conversations by retention: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()
