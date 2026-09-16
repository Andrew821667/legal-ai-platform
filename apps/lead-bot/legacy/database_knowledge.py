"""Диалоги для RAG: примеры удачных разговоров к промпту помощника.

Лиды берутся из ядра (см. core_leads), сами сообщения — из локальной
таблицы conversations: переписка с ботом живёт здесь.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)


def conversations_for_users(
    get_connection: Callable[[], sqlite3.Connection],
    user_ids: list[int],
) -> dict[int, list[dict]]:
    """Сообщения указанных пользователей, по порядку, сгруппированные по user_id."""
    if not user_ids:
        return {}
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in user_ids)
        rows = conn.execute(
            f"""
            SELECT user_id, role, message, timestamp
            FROM conversations
            WHERE user_id IN ({placeholders})
            ORDER BY user_id ASC, timestamp ASC
            """,
            list(user_ids),
        ).fetchall()
    finally:
        conn.close()
    messages_by_user: dict[int, list[dict]] = {}
    for row in rows:
        payload = dict(row)
        messages_by_user.setdefault(payload["user_id"], []).append(
            {"role": payload["role"], "message": payload["message"], "timestamp": payload["timestamp"]}
        )
    return messages_by_user


def get_successful_conversations(
    get_connection: Callable[[], sqlite3.Connection],
    leads: list[dict],
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Тёплые и горячие лиды с содержательной анкетой — вместе с их перепиской."""
    chosen = [
        lead
        for lead in leads
        if lead.get("temperature") in ("warm", "hot")
        and (lead.get("service_category") or lead.get("pain_point"))
        and lead.get("user_id")
    ]
    chosen.sort(key=lambda lead: str(lead.get("created_at") or ""), reverse=True)
    chosen = chosen[max(0, int(offset)) : max(0, int(offset)) + max(1, int(limit))]
    if not chosen:
        return []
    messages_by_user = conversations_for_users(get_connection, [lead["user_id"] for lead in chosen])
    result = [
        {
            "lead_id": lead["id"],
            "user_id": lead["user_id"],
            "service_category": lead.get("service_category"),
            "specific_need": lead.get("specific_need"),
            "pain_point": lead.get("pain_point"),
            "industry": lead.get("industry"),
            "temperature": lead.get("temperature"),
            "messages": messages_by_user.get(lead["user_id"], []),
        }
        for lead in chosen
    ]
    logger.info("Retrieved %s successful conversations for RAG", len(result))
    return result


def get_conversations_by_category(
    get_connection: Callable[[], sqlite3.Connection],
    leads: list[dict],
    *,
    service_category: str,
    temperature: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Переписка по категории услуги, при желании — только заданной температуры."""
    chosen = [
        lead
        for lead in leads
        if lead.get("service_category") == service_category
        and (temperature is None or lead.get("temperature") == temperature)
        and lead.get("user_id")
    ]
    chosen.sort(key=lambda lead: str(lead.get("created_at") or ""), reverse=True)
    chosen = chosen[: max(1, int(limit))]
    if not chosen:
        return []
    messages_by_user = conversations_for_users(get_connection, [lead["user_id"] for lead in chosen])
    return [
        {
            "lead_id": lead["id"],
            "service_category": lead.get("service_category"),
            "specific_need": lead.get("specific_need"),
            "pain_point": lead.get("pain_point"),
            "temperature": lead.get("temperature"),
            "messages": messages_by_user.get(lead["user_id"], []),
        }
        for lead in chosen
    ]
