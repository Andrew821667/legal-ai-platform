"""
Analytics event and reporting helpers extracted from the legacy Database class.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)


def track_event(
    get_connection: Callable[[], sqlite3.Connection],
    get_lead_by_id: Callable[[int], dict | None],
    *,
    user_id: int,
    event_type: str,
    payload: dict | None = None,
    lead_id: int | None = None,
) -> int:
    """Persist analytics event locally and mirror it to core-api when possible."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        payload_text = json.dumps(payload or {}, ensure_ascii=False)
        cursor.execute(
            """
            INSERT INTO analytics_events (user_id, lead_id, event_type, event_payload)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, lead_id, event_type, payload_text),
        )
        conn.commit()
        event_row_id = cursor.lastrowid
    except Exception as error:
        logger.error("Error tracking analytics event: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()

    try:
        from core_api_bridge import core_api_bridge

        core_lead_id = None
        if lead_id:
            lead = get_lead_by_id(lead_id) or {}
            core_lead_id = lead.get("core_lead_id")
        core_api_bridge.track_event(
            event_type=event_type,
            payload={
                **(payload or {}),
                "legacy_event_id": event_row_id,
                "legacy_user_id": user_id,
                "legacy_lead_id": lead_id,
            },
            idempotency_key=f"legacy-event-sync-{event_row_id}",
            core_lead_id=core_lead_id,
        )
    except Exception as mirror_error:
        logger.warning("Failed to mirror analytics event %s to core-api: %s", event_type, mirror_error)

    return event_row_id


def get_statistics(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    days: int = 30,
) -> dict:
    """Return a compact statistics snapshot for admin/reporting."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        stats: dict[str, int | float] = {}

        cursor.execute("SELECT COUNT(*) FROM users")
        stats["total_users"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM users
            WHERE created_at >= datetime('now', '-' || ? || ' days')
            """,
            (days,),
        )
        stats["new_users"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads")
        stats["total_leads"] = cursor.fetchone()[0]

        for temp in ["hot", "warm", "cold"]:
            cursor.execute("SELECT COUNT(*) FROM leads WHERE temperature = ?", (temp,))
            stats[f"{temp}_leads"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM conversations")
        stats["total_messages"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT AVG(msg_count)
            FROM (
                SELECT user_id, COUNT(*) as msg_count
                FROM conversations
                GROUP BY user_id
            )
            """
        )
        result = cursor.fetchone()[0]
        stats["avg_conversation_length"] = round(result, 1) if result else 0

        cursor.execute("SELECT COUNT(*) FROM leads WHERE lead_magnet_type = 'consultation'")
        stats["consultations"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE lead_magnet_type = 'checklist'")
        stats["checklists"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE lead_magnet_type IN ('demo', 'demo_analysis')")
        stats["demos"] = cursor.fetchone()[0]

        for stage in ["discover", "diagnose", "qualify", "propose", "handoff"]:
            cursor.execute("SELECT COUNT(*) FROM users WHERE conversation_stage = ?", (stage,))
            stats[f"stage_{stage}"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE cta_shown = 1")
        stats["cta_shown_users"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM analytics_events
            WHERE event_type = 'cta_clicked'
            """
        )
        stats["cta_clicks"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM analytics_events
            WHERE event_type = 'handoff_done'
            """
        )
        stats["handoff_done"] = cursor.fetchone()[0]

        return stats
    finally:
        conn.close()


def get_funnel_report(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    days: int = 30,
) -> dict:
    """Return SQL funnel report for the given time window."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        report: dict[str, dict] = {}
        window = str(days)

        cursor.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM conversations
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
            """,
            (window,),
        )
        discover_users = cursor.fetchone()[0] or 0

        stage_counts = {"discover": discover_users}
        for stage in ("diagnose", "qualify", "propose", "handoff"):
            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM analytics_events
                WHERE event_type = 'stage_changed'
                  AND created_at >= datetime('now', '-' || ? || ' days')
                  AND event_payload LIKE ?
                """,
                (window, f'%"to": "{stage}"%'),
            )
            stage_counts[stage] = cursor.fetchone()[0] or 0

        cursor.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM analytics_events
            WHERE event_type = 'cta_shown'
              AND created_at >= datetime('now', '-' || ? || ' days')
            """,
            (window,),
        )
        cta_shown_users = cursor.fetchone()[0] or 0

        cursor.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM analytics_events
            WHERE event_type = 'cta_clicked'
              AND created_at >= datetime('now', '-' || ? || ' days')
            """,
            (window,),
        )
        cta_clicked_users = cursor.fetchone()[0] or 0

        cursor.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM analytics_events
            WHERE event_type = 'handoff_done'
              AND created_at >= datetime('now', '-' || ? || ' days')
            """,
            (window,),
        )
        handoff_users = cursor.fetchone()[0] or 0

        def _rate(num: int, den: int) -> float:
            if not den:
                return 0.0
            return round((num / den) * 100.0, 1)

        transitions = {
            "discover_to_diagnose": _rate(stage_counts["diagnose"], stage_counts["discover"]),
            "diagnose_to_qualify": _rate(stage_counts["qualify"], stage_counts["diagnose"]),
            "qualify_to_propose": _rate(stage_counts["propose"], stage_counts["qualify"]),
            "propose_to_handoff": _rate(stage_counts["handoff"], stage_counts["propose"]),
            "cta_click_from_shown": _rate(cta_clicked_users, cta_shown_users),
            "handoff_from_shown": _rate(handoff_users, cta_shown_users),
        }

        report["stage_counts"] = stage_counts
        report["event_counts"] = {
            "cta_shown_users": cta_shown_users,
            "cta_clicked_users": cta_clicked_users,
            "handoff_users": handoff_users,
        }
        report["transitions"] = transitions
        report["window_days"] = days
        return report
    finally:
        conn.close()


def get_ab_cta_report(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    days: int = 30,
) -> dict:
    """Return A/B CTA report for the selected window."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        window = str(days)
        variants: dict[str, dict] = {}

        def _count_users(event_type: str, pattern: str) -> int:
            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM analytics_events
                WHERE event_type = ?
                  AND created_at >= datetime('now', '-' || ? || ' days')
                  AND event_payload LIKE ?
                """,
                (event_type, window, pattern),
            )
            return cursor.fetchone()[0] or 0

        def _rate(num: int, den: int) -> float:
            if not den:
                return 0.0
            return round((num / den) * 100.0, 1)

        for variant in ("A", "B"):
            shown = _count_users("cta_shown", f'%"variant": "{variant}"%')
            clicked = _count_users("cta_clicked", f'%"variant": "{variant}"%')
            handoff = _count_users("handoff_done", f'%"cta_variant": "{variant}"%')
            variants[variant] = {
                "shown_users": shown,
                "clicked_users": clicked,
                "handoff_users": handoff,
                "click_rate": _rate(clicked, shown),
                "handoff_rate": _rate(handoff, shown),
            }

        total = {
            "shown_users": variants["A"]["shown_users"] + variants["B"]["shown_users"],
            "clicked_users": variants["A"]["clicked_users"] + variants["B"]["clicked_users"],
            "handoff_users": variants["A"]["handoff_users"] + variants["B"]["handoff_users"],
        }
        total["click_rate"] = _rate(total["clicked_users"], total["shown_users"])
        total["handoff_rate"] = _rate(total["handoff_users"], total["shown_users"])

        return {"window_days": days, "variants": variants, "total": total}
    finally:
        conn.close()
