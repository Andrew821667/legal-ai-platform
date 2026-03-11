"""
User state and funnel helpers extracted from the legacy Database class.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)


def reset_user_to_new_state(
    get_connection: Callable[[], sqlite3.Connection],
    sync_user_to_core: Callable[[int], None],
    *,
    user_id: int,
) -> dict:
    """
    Reset a user to the initial state while preserving identity profile fields.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT telegram_id FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return {
                "users_reset": 0,
                "leads_deleted": 0,
                "messages_deleted": 0,
                "events_deleted": 0,
            }

        telegram_id = row[0]
        cursor.execute("SELECT id FROM leads WHERE user_id = ?", (user_id,))
        lead_ids = [int(item[0]) for item in cursor.fetchall()]

        notifications_deleted = 0
        if lead_ids:
            placeholders = ",".join("?" for _ in lead_ids)
            cursor.execute(
                f"DELETE FROM admin_notifications WHERE lead_id IN ({placeholders})",
                lead_ids,
            )
            notifications_deleted = cursor.rowcount

        cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        messages_deleted = cursor.rowcount

        cursor.execute("DELETE FROM analytics_events WHERE user_id = ?", (user_id,))
        events_deleted = cursor.rowcount

        cursor.execute("DELETE FROM leads WHERE user_id = ?", (user_id,))
        leads_deleted = cursor.rowcount

        cursor.execute(
            """
            UPDATE users
            SET consent_given = 0,
                consent_date = NULL,
                consent_revoked = 0,
                consent_revoked_at = NULL,
                transborder_consent = 0,
                transborder_consent_date = NULL,
                marketing_consent = 0,
                marketing_consent_date = NULL,
                conversation_stage = 'discover',
                cta_variant = NULL,
                cta_shown = 0,
                cta_shown_at = NULL,
                last_interaction = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,),
        )
        users_reset = cursor.rowcount

        chat_states_cleared = 0
        business_states_cleared = 0
        if telegram_id is not None:
            cursor.execute("DELETE FROM chat_states WHERE chat_id = ?", (int(telegram_id),))
            chat_states_cleared = cursor.rowcount
            cursor.execute("DELETE FROM business_connection_states WHERE user_chat_id = ?", (int(telegram_id),))
            business_states_cleared = cursor.rowcount

        conn.commit()
        sync_user_to_core(user_id)
        return {
            "users_reset": users_reset,
            "leads_deleted": leads_deleted,
            "messages_deleted": messages_deleted,
            "events_deleted": events_deleted,
            "notifications_deleted": notifications_deleted,
            "chat_states_cleared": chat_states_cleared,
            "business_states_cleared": business_states_cleared,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_user_completely(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    user_id: int,
) -> dict:
    """Delete a user and all related records."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT telegram_id FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return {
                "users_deleted": 0,
                "leads_deleted": 0,
                "messages_deleted": 0,
                "events_deleted": 0,
            }

        telegram_id = row[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE user_id = ?", (user_id,))
        leads_deleted = int((cursor.fetchone() or [0])[0])

        cursor.execute("SELECT COUNT(*) FROM conversations WHERE user_id = ?", (user_id,))
        messages_deleted = int((cursor.fetchone() or [0])[0])

        cursor.execute("SELECT COUNT(*) FROM analytics_events WHERE user_id = ?", (user_id,))
        events_deleted = int((cursor.fetchone() or [0])[0])

        cursor.execute("SELECT id FROM leads WHERE user_id = ?", (user_id,))
        lead_ids = [int(item[0]) for item in cursor.fetchall()]
        notifications_deleted = 0
        if lead_ids:
            placeholders = ",".join("?" for _ in lead_ids)
            cursor.execute(
                f"DELETE FROM admin_notifications WHERE lead_id IN ({placeholders})",
                lead_ids,
            )
            notifications_deleted = cursor.rowcount

        cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM analytics_events WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM leads WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        users_deleted = cursor.rowcount

        chat_states_deleted = 0
        business_states_deleted = 0
        if telegram_id is not None:
            cursor.execute("DELETE FROM chat_states WHERE chat_id = ?", (int(telegram_id),))
            chat_states_deleted = cursor.rowcount
            cursor.execute("DELETE FROM business_connection_states WHERE user_chat_id = ?", (int(telegram_id),))
            business_states_deleted = cursor.rowcount

        conn.commit()
        return {
            "users_deleted": users_deleted,
            "leads_deleted": leads_deleted,
            "messages_deleted": messages_deleted,
            "events_deleted": events_deleted,
            "notifications_deleted": notifications_deleted,
            "chat_states_deleted": chat_states_deleted,
            "business_states_deleted": business_states_deleted,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_user_fields(
    get_connection: Callable[[], sqlite3.Connection],
    sync_user_to_core: Callable[[int], None],
    validate_columns: Callable[[object, frozenset, str], None],
    users_columns: frozenset,
    *,
    user_id: int,
    fields: dict[str, str],
) -> bool:
    """Update allowed user profile fields."""
    if not fields:
        return False
    validate_columns(fields.keys(), users_columns, "update_user_fields")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        set_clause = ", ".join(f"{key} = ?" for key in fields.keys())
        values = list(fields.values()) + [user_id]
        cursor.execute(
            f"UPDATE users SET {set_clause}, last_interaction = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        conn.commit()
        if cursor.rowcount > 0:
            sync_user_to_core(user_id)
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_funnel_state(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    user_id: int,
) -> dict:
    """Return current funnel state for the user."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT conversation_stage, cta_variant, cta_shown, cta_shown_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return {
                "conversation_stage": "discover",
                "cta_variant": None,
                "cta_shown": False,
                "cta_shown_at": None,
            }
        data = dict(row)
        return {
            "conversation_stage": data.get("conversation_stage") or "discover",
            "cta_variant": data.get("cta_variant"),
            "cta_shown": bool(data.get("cta_shown")),
            "cta_shown_at": data.get("cta_shown_at"),
        }
    finally:
        conn.close()


def update_user_funnel_state(
    get_connection: Callable[[], sqlite3.Connection],
    sync_user_to_core: Callable[[int], None],
    *,
    user_id: int,
    conversation_stage: str | None = None,
    cta_variant: str | None = None,
    cta_shown: bool | None = None,
) -> None:
    """Update funnel state in the users table."""
    updates: list[str] = []
    values: list[object] = []

    if conversation_stage is not None:
        updates.append("conversation_stage = ?")
        values.append(conversation_stage)

    if cta_variant is not None:
        updates.append("cta_variant = ?")
        values.append(cta_variant)

    if cta_shown is not None:
        updates.append("cta_shown = ?")
        values.append(1 if cta_shown else 0)
        updates.append("cta_shown_at = CURRENT_TIMESTAMP" if cta_shown else "cta_shown_at = NULL")

    if not updates:
        return

    conn = get_connection()
    cursor = conn.cursor()
    try:
        values.append(user_id)
        cursor.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        conn.commit()
        sync_user_to_core(user_id)
    except Exception as error:
        logger.error("Error updating user funnel state: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_user_funnel_state(
    get_connection: Callable[[], sqlite3.Connection],
    sync_user_to_core: Callable[[int], None],
    *,
    user_id: int,
) -> None:
    """Reset funnel state for both user and latest lead row."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET conversation_stage = 'discover',
                cta_shown = 0,
                cta_shown_at = NULL
            WHERE id = ?
            """,
            (user_id,),
        )
        cursor.execute(
            """
            UPDATE leads
            SET conversation_stage = 'discover',
                cta_shown = 0
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()
        sync_user_to_core(user_id)
    except Exception as error:
        logger.error("Error resetting user funnel state: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()
