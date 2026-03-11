"""
Local user-profile helpers extracted from the legacy Database class.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

import utils

logger = logging.getLogger(__name__)


def create_or_update_user(
    get_connection: Callable[[], sqlite3.Connection],
    sync_user_to_core: Callable[[int], None],
    *,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id, username, first_name, last_name FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        existing_row = cursor.fetchone()
        profile_changed = (
            existing_row is None
            or (existing_row["username"] or None) != (username or None)
            or (existing_row["first_name"] or None) != (first_name or None)
            or (existing_row["last_name"] or None) != (last_name or None)
        )
        cursor.execute(
            """
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                last_interaction = CURRENT_TIMESTAMP
            """,
            (telegram_id, username, first_name, last_name),
        )

        conn.commit()

        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        user_id = cursor.fetchone()[0]

        logger.info("User %s created/updated with id %s", utils.mask_telegram_id(telegram_id), user_id)
        if profile_changed:
            sync_user_to_core(user_id)
        return int(user_id)
    except Exception as error:
        logger.error("Error creating/updating user: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def get_local_user_by_telegram_id(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_id: int,
) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_local_user_by_id(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    user_id: int,
) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_offer_profile(
    get_local_user_by_id_func: Callable[[int], dict | None],
    *,
    user_id: int,
) -> str | None:
    user = get_local_user_by_id_func(user_id)
    if not user:
        return None
    value = user.get("offer_profile_override")
    return str(value) if value else None


def set_user_offer_profile(
    get_connection: Callable[[], sqlite3.Connection],
    sync_user_to_core: Callable[[int], None],
    *,
    user_id: int,
    profile_key: str | None,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET offer_profile_override = ?,
                last_interaction = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (profile_key, user_id),
        )
        conn.commit()
        sync_user_to_core(user_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_recent_users(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM users
            ORDER BY COALESCE(last_interaction, created_at) DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (max(1, int(limit)), max(0, int(offset))),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def count_users(get_connection: Callable[[], sqlite3.Connection]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        row = cursor.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def get_users_without_consent(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    limit: int = 20,
) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE COALESCE(consent_given, 0) = 0
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_users_with_revoked_consent(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    limit: int = 20,
) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE COALESCE(consent_revoked, 0) = 1
            ORDER BY COALESCE(consent_revoked_at, last_interaction, created_at) DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
