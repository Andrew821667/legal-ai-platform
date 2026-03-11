"""
Lead and admin-notification helpers extracted from the legacy Database class.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)


def update_lead_funnel_state(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    user_id: int,
    conversation_stage: str | None = None,
    cta_variant: str | None = None,
    cta_shown: bool | None = None,
) -> None:
    """Sync funnel state to the latest lead row for the user."""
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

    if not updates:
        return

    conn = get_connection()
    cursor = conn.cursor()
    try:
        values.append(user_id)
        cursor.execute(
            (
                f"UPDATE leads SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ("
                "SELECT id FROM leads "
                "WHERE user_id = ? "
                "ORDER BY updated_at DESC, created_at DESC, id DESC "
                "LIMIT 1"
                ")"
            ),
            values,
        )
        conn.commit()
    except Exception as error:
        logger.error("Error updating lead funnel state: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def update_lead_funnel_state_by_id(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    lead_id: int,
    conversation_stage: str | None = None,
    cta_variant: str | None = None,
    cta_shown: bool | None = None,
) -> None:
    """Sync funnel state to a specific lead row."""
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

    if not updates:
        return

    conn = get_connection()
    cursor = conn.cursor()
    try:
        values.append(lead_id)
        cursor.execute(
            f"UPDATE leads SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        conn.commit()
    except Exception as error:
        logger.error("Error updating lead funnel state by id: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def create_or_update_lead(
    get_connection: Callable[[], sqlite3.Connection],
    sync_lead_to_core: Callable[[int], None],
    leads_columns: frozenset,
    *,
    user_id: int,
    lead_data: dict,
) -> int:
    """Create or update a lead row for the user."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        company = lead_data.get("company")
        email = lead_data.get("email")

        if company and email:
            cursor.execute(
                "SELECT id FROM leads WHERE user_id = ? AND company = ? AND email = ?",
                (user_id, company, email),
            )
        else:
            cursor.execute(
                "SELECT id FROM leads WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            )

        existing = cursor.fetchone()

        if existing:
            lead_id = existing[0]
            safe_data = {key: value for key, value in lead_data.items() if value is not None and key in leads_columns}
            if safe_data:
                update_fields = [f"{key} = ?" for key in safe_data]
                values = list(safe_data.values()) + [lead_id]
                query = f"UPDATE leads SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                cursor.execute(query, values)
            logger.info("Lead %s updated for user %s", lead_id, user_id)
        else:
            safe_data = {key: value for key, value in lead_data.items() if key in leads_columns}
            fields = ["user_id"] + list(safe_data.keys())
            placeholders = ["?"] * len(fields)
            values = [user_id] + list(safe_data.values())
            query = f"INSERT INTO leads ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(query, values)
            lead_id = cursor.lastrowid
            logger.info("Lead %s created for user %s", lead_id, user_id)

        conn.commit()
        sync_lead_to_core(lead_id)
        return lead_id
    except Exception as error:
        logger.error("Error creating/updating lead: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def create_new_lead(
    get_connection: Callable[[], sqlite3.Connection],
    sync_lead_to_core: Callable[[int], None],
    leads_columns: frozenset,
    *,
    user_id: int,
    lead_data: dict,
) -> int:
    """Force creation of a new lead row without merging."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cleaned = {key: value for key, value in (lead_data or {}).items() if value is not None and key in leads_columns}
        fields = ["user_id"] + list(cleaned.keys())
        values = [user_id] + list(cleaned.values())
        placeholders = ["?"] * len(fields)

        query = f"INSERT INTO leads ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(query, values)
        lead_id = cursor.lastrowid
        conn.commit()
        logger.info("New lead %s created for user %s", lead_id, user_id)
        sync_lead_to_core(lead_id)
        return lead_id
    except Exception as error:
        logger.error("Error creating new lead: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def get_local_lead_by_user_id(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    user_id: int,
) -> dict | None:
    """Return the latest local lead snapshot without core-api merge."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM leads
            WHERE user_id = ?
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_lead_by_user_id(
    get_connection: Callable[[], sqlite3.Connection],
    get_local_user_by_id: Callable[[int], dict | None],
    merge_lead_row_with_core: Callable[[dict | None, int | None], dict | None],
    *,
    user_id: int,
) -> dict | None:
    """Return the latest lead merged with core-api when available."""
    lead = get_local_lead_by_user_id(get_connection, user_id=user_id)
    if not lead:
        return None
    user = get_local_user_by_id(user_id)
    telegram_user_id = (user or {}).get("telegram_id")
    return merge_lead_row_with_core(lead, telegram_user_id=telegram_user_id)


def mark_lead_notification_sent(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    lead_id: int,
) -> None:
    """Mark admin notification as already sent for the lead."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE leads
            SET notification_sent = 1
            WHERE id = ?
            """,
            (lead_id,),
        )
        conn.commit()
        logger.info("Lead %s marked as notification sent", lead_id)
    except Exception as error:
        logger.error("Error marking lead notification sent: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()


def get_lead_by_id(
    get_connection: Callable[[], sqlite3.Connection],
    get_user_by_id: Callable[[int], dict | None],
    merge_lead_row_with_core: Callable[[dict | None, int | None], dict | None],
    *,
    lead_id: int,
) -> dict | None:
    """Return lead by internal id, merged with core-api when available."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        row = cursor.fetchone()
        if not row:
            return None
        local_lead = dict(row)
        user = get_user_by_id(local_lead["user_id"]) if local_lead.get("user_id") else None
        return merge_lead_row_with_core(local_lead, telegram_user_id=(user or {}).get("telegram_id"))
    finally:
        conn.close()


def set_core_lead_id(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    lead_id: int,
    core_lead_id: str,
) -> None:
    """Persist the core-api UUID for a legacy lead row."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE leads
            SET core_lead_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (core_lead_id, lead_id),
        )
        conn.commit()
    except Exception as error:
        logger.error("Error setting core_lead_id for lead %s: %s", lead_id, error)
        conn.rollback()
        raise
    finally:
        conn.close()


def get_all_leads(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    temperature: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Return leads with optional temperature/status filters."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM leads WHERE 1=1"
        params: list[object] = []

        if temperature:
            query += " AND temperature = ?"
            params.append(temperature)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.append(max(1, int(limit)))
        params.append(max(0, int(offset)))

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_leads_ready_for_notification(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    idle_minutes: int = 5,
) -> list[dict]:
    """Return warm/hot leads idle long enough for admin notification."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT * FROM leads
            WHERE last_message_at IS NOT NULL
              AND notification_sent = 0
              AND datetime(last_message_at, '+' || ? || ' minutes') <= datetime('now')
              AND (
                    temperature IN ('warm', 'hot')
                    OR (
                        name IS NOT NULL
                        AND (email IS NOT NULL OR phone IS NOT NULL)
                        AND pain_point IS NOT NULL
                    )
              )
            ORDER BY last_message_at DESC
            """,
            (str(int(idle_minutes)),),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_lead_last_message_time(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    user_id: int,
) -> None:
    """Touch the last_message_at field for all user leads."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE leads
            SET last_message_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()
        logger.debug("Updated last_message_at for user %s", user_id)
    except Exception as error:
        logger.error("Error updating last_message_at: %s", error)
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
