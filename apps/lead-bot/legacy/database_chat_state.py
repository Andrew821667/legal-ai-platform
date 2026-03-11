"""
Chat and business-connection state helpers extracted from the legacy Database class.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)


def is_chat_enabled(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    chat_id: int,
) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT is_enabled FROM chat_states WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        return bool(row[0]) if row else True
    finally:
        conn.close()


def set_chat_enabled(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    chat_id: int,
    enabled: bool,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO chat_states (chat_id, is_enabled, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                is_enabled = excluded.is_enabled,
                updated_at = CURRENT_TIMESTAMP
            """,
            (chat_id, 1 if enabled else 0),
        )
        conn.commit()
        logger.info("Chat %s %s", chat_id, "enabled" if enabled else "disabled")
    except Exception as error:
        logger.error("Error setting chat enabled state: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def get_chat_mode(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    chat_id: int,
) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT mode FROM chat_states WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        mode = (row[0] if row and row[0] else "bot").strip().lower()
        return mode if mode in {"bot", "personal"} else "bot"
    finally:
        conn.close()


def set_chat_mode(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    chat_id: int,
    mode: str,
) -> None:
    normalized_mode = (mode or "bot").strip().lower()
    if normalized_mode not in {"bot", "personal"}:
        normalized_mode = "bot"

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO chat_states (chat_id, is_enabled, mode, updated_at)
            VALUES (?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                mode = excluded.mode,
                updated_at = CURRENT_TIMESTAMP
            """,
            (chat_id, normalized_mode),
        )
        conn.commit()
        logger.info("Chat %s switched to mode=%s", chat_id, normalized_mode)
    except Exception as error:
        logger.error("Error setting chat mode: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def get_disabled_chats(get_connection: Callable[[], sqlite3.Connection]) -> list[int]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT chat_id FROM chat_states WHERE is_enabled = 0")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def set_business_connection_state(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    connection_id: str,
    user_chat_id: int | None,
    is_enabled: bool,
) -> None:
    if not connection_id:
        return
    connection_key = str(connection_id)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO business_connection_states (connection_id, user_chat_id, is_enabled, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(connection_id) DO UPDATE SET
                user_chat_id = excluded.user_chat_id,
                is_enabled = excluded.is_enabled,
                updated_at = CURRENT_TIMESTAMP
            """,
            (connection_key, user_chat_id, 1 if is_enabled else 0),
        )
        conn.commit()
        logger.info(
            "Business connection %s for user_chat_id=%s set to %s",
            connection_key,
            user_chat_id,
            "enabled" if is_enabled else "disabled",
        )
    except Exception as error:
        logger.error("Error setting business connection state: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def is_business_connection_enabled(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    connection_id: str | None,
) -> bool:
    if not connection_id:
        return True
    connection_key = str(connection_id)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT is_enabled FROM business_connection_states WHERE connection_id = ?",
            (connection_key,),
        )
        row = cursor.fetchone()
        return bool(row[0]) if row else True
    finally:
        conn.close()
