"""
Consent and export helpers extracted from the legacy Database class.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)


def _build_consent_payload(user: dict | None) -> dict:
    if not user:
        return {}
    return {
        "consent_given": bool(user.get("consent_given")),
        "consent_date": user.get("consent_date"),
        "consent_revoked": bool(user.get("consent_revoked")),
        "consent_revoked_at": user.get("consent_revoked_at"),
        "transborder_consent": bool(user.get("transborder_consent")),
        "transborder_consent_date": user.get("transborder_consent_date"),
        "marketing_consent": bool(user.get("marketing_consent")),
        "marketing_consent_date": user.get("marketing_consent_date"),
    }


def get_user_consent_state(
    get_local_user_by_id: Callable[[int], dict | None],
    *,
    user_id: int,
) -> dict:
    """Return current consent flags for the user."""
    user = get_local_user_by_id(user_id)
    return _build_consent_payload(user)


def grant_user_consent(
    get_connection: Callable[[], sqlite3.Connection],
    sync_user_to_core: Callable[[int], None],
    *,
    user_id: int,
) -> None:
    """Grant base personal data consent."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET consent_given = 1,
                consent_date = CURRENT_TIMESTAMP,
                consent_revoked = 0,
                consent_revoked_at = NULL,
                last_interaction = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,),
        )
        conn.commit()
        sync_user_to_core(user_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_user_transborder_consent(
    get_connection: Callable[[], sqlite3.Connection],
    sync_user_to_core: Callable[[int], None],
    *,
    user_id: int,
    granted: bool,
) -> None:
    """Update consent for transborder processing."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET transborder_consent = ?,
                transborder_consent_date = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,
                last_interaction = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if granted else 0, 1 if granted else 0, user_id),
        )
        conn.commit()
        sync_user_to_core(user_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_user_marketing_consent(
    get_connection: Callable[[], sqlite3.Connection],
    sync_user_to_core: Callable[[int], None],
    *,
    user_id: int,
    granted: bool,
) -> None:
    """Update consent for marketing communication."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET marketing_consent = ?,
                marketing_consent_date = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,
                last_interaction = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if granted else 0, 1 if granted else 0, user_id),
        )
        conn.commit()
        sync_user_to_core(user_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def revoke_user_consent_and_delete_data(
    get_connection: Callable[[], sqlite3.Connection],
    sync_user_to_core: Callable[[int], None],
    sync_lead_to_core: Callable[[int], None],
    *,
    user_id: int,
) -> dict:
    """
    Revoke consents, anonymize lead PD and delete conversation history.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET consent_given = 0,
                consent_revoked = 1,
                consent_revoked_at = CURRENT_TIMESTAMP,
                transborder_consent = 0,
                transborder_consent_date = NULL,
                marketing_consent = 0,
                marketing_consent_date = NULL,
                last_interaction = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,),
        )
        users_updated = cursor.rowcount

        cursor.execute(
            """
            UPDATE leads
            SET name = 'Анонимизировано',
                email = NULL,
                phone = NULL,
                company = NULL,
                notes = COALESCE(notes, '') || '\n[PDN] Анонимизировано по запросу пользователя',
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )
        leads_anonymized = cursor.rowcount

        cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        messages_deleted = cursor.rowcount

        cursor.execute("SELECT id FROM leads WHERE user_id = ?", (user_id,))
        affected_lead_ids = [row[0] for row in cursor.fetchall()]

        conn.commit()
        sync_user_to_core(user_id)
        for lead_id in affected_lead_ids:
            sync_lead_to_core(int(lead_id))
        return {
            "users_updated": users_updated,
            "leads_anonymized": leads_anonymized,
            "messages_deleted": messages_deleted,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def export_user_data(
    get_user_by_id: Callable[[int], dict | None],
    get_lead_by_user_id: Callable[[int], dict | None],
    *,
    user_id: int,
) -> dict:
    """Export user profile, lead data and consent flags."""
    user = get_user_by_id(user_id)
    if not user:
        return {}
    lead = get_lead_by_user_id(user_id)
    return {
        "user": user,
        "lead": lead or {},
        "consent": _build_consent_payload(user),
    }
