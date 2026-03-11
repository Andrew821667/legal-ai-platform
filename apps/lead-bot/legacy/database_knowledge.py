"""
Knowledge-base and RAG helpers extracted from the legacy Database class.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)


def get_successful_conversations(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return successful warm/hot conversations for the RAG layer."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                l.*,
                u.telegram_id,
                u.username,
                u.first_name
            FROM leads l
            JOIN users u ON l.user_id = u.id
            WHERE l.temperature IN ('warm', 'hot')
              AND (l.service_category IS NOT NULL OR l.pain_point IS NOT NULL)
            ORDER BY l.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (max(1, int(limit)), max(0, int(offset))),
        )

        leads = [dict(row) for row in cursor.fetchall()]
        if not leads:
            return []

        user_ids = [lead["user_id"] for lead in leads]
        placeholders = ",".join("?" for _ in user_ids)
        cursor.execute(
            f"""
            SELECT user_id, role, message, timestamp
            FROM conversations
            WHERE user_id IN ({placeholders})
            ORDER BY user_id ASC, timestamp ASC
            """,
            user_ids,
        )

        messages_by_user: dict[int, list[dict]] = {}
        for row in cursor.fetchall():
            payload = dict(row)
            messages_by_user.setdefault(payload["user_id"], []).append(
                {
                    "role": payload["role"],
                    "message": payload["message"],
                    "timestamp": payload["timestamp"],
                }
            )

        result = []
        for lead in leads:
            user_id = lead["user_id"]
            result.append(
                {
                    "lead_id": lead["id"],
                    "user_id": user_id,
                    "service_category": lead.get("service_category"),
                    "specific_need": lead.get("specific_need"),
                    "pain_point": lead.get("pain_point"),
                    "industry": lead.get("industry"),
                    "temperature": lead.get("temperature"),
                    "messages": messages_by_user.get(user_id, []),
                }
            )

        logger.info("Retrieved %s successful conversations for RAG", len(result))
        return result
    finally:
        conn.close()


def get_conversations_by_category(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    service_category: str,
    temperature: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Return conversations filtered by service category and optional temperature."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT
                l.*,
                u.telegram_id,
                u.first_name
            FROM leads l
            JOIN users u ON l.user_id = u.id
            WHERE l.service_category = ?
        """
        params: list[object] = [service_category]

        if temperature:
            query += " AND l.temperature = ?"
            params.append(temperature)

        query += " ORDER BY l.created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        leads = [dict(row) for row in cursor.fetchall()]
        if not leads:
            return []

        user_ids = [lead["user_id"] for lead in leads]
        placeholders = ",".join("?" for _ in user_ids)
        cursor.execute(
            f"""
            SELECT user_id, role, message, timestamp
            FROM conversations
            WHERE user_id IN ({placeholders})
            ORDER BY user_id ASC, timestamp ASC
            """,
            user_ids,
        )

        messages_by_user: dict[int, list[dict]] = {}
        for row in cursor.fetchall():
            payload = dict(row)
            messages_by_user.setdefault(payload["user_id"], []).append(
                {
                    "role": payload["role"],
                    "message": payload["message"],
                    "timestamp": payload["timestamp"],
                }
            )

        result = []
        for lead in leads:
            result.append(
                {
                    "lead_id": lead["id"],
                    "service_category": lead.get("service_category"),
                    "specific_need": lead.get("specific_need"),
                    "pain_point": lead.get("pain_point"),
                    "temperature": lead.get("temperature"),
                    "messages": messages_by_user.get(lead["user_id"], []),
                }
            )

        return result
    finally:
        conn.close()
