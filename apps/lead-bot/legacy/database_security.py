"""
Persistent security and anti-abuse helpers extracted from the legacy Database class.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Callable


def record_security_message_event(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    ts_epoch: int,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO security_message_events (telegram_user_id, ts_epoch)
            VALUES (?, ?)
            """,
            (int(telegram_user_id), int(ts_epoch)),
        )
        conn.commit()
    finally:
        conn.close()


def prune_security_message_events(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    older_than_epoch: int,
    telegram_user_id: int | None = None,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if telegram_user_id is None:
            cursor.execute(
                "DELETE FROM security_message_events WHERE ts_epoch < ?",
                (int(older_than_epoch),),
            )
        else:
            cursor.execute(
                "DELETE FROM security_message_events WHERE telegram_user_id = ? AND ts_epoch < ?",
                (int(telegram_user_id), int(older_than_epoch)),
            )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def count_security_message_events_since(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    since_epoch: int,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM security_message_events
            WHERE telegram_user_id = ? AND ts_epoch > ?
            """,
            (int(telegram_user_id), int(since_epoch)),
        )
        row = cursor.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def add_security_tokens_used(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    date_key: str,
    tokens: int,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO security_token_usage_daily (telegram_user_id, date_key, tokens_used, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_user_id, date_key) DO UPDATE SET
                tokens_used = security_token_usage_daily.tokens_used + excluded.tokens_used,
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(telegram_user_id), str(date_key), int(tokens)),
        )
        conn.commit()
    finally:
        conn.close()


def get_security_user_tokens(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    date_key: str,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT tokens_used
            FROM security_token_usage_daily
            WHERE telegram_user_id = ? AND date_key = ?
            """,
            (int(telegram_user_id), str(date_key)),
        )
        row = cursor.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def get_security_user_tokens_since(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    start_date_key: str,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT COALESCE(SUM(tokens_used), 0)
            FROM security_token_usage_daily
            WHERE telegram_user_id = ? AND date_key >= ?
            """,
            (int(telegram_user_id), str(start_date_key)),
        )
        row = cursor.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def get_security_total_tokens(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    date_key: str,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT COALESCE(SUM(tokens_used), 0)
            FROM security_token_usage_daily
            WHERE date_key = ?
            """,
            (str(date_key),),
        )
        row = cursor.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def add_security_blacklist(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    reason: str = "",
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO security_blacklist (telegram_user_id, reason, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                reason = excluded.reason,
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(telegram_user_id), str(reason or "").strip()),
        )
        conn.commit()
    finally:
        conn.close()


def remove_security_blacklist(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM security_blacklist WHERE telegram_user_id = ?",
            (int(telegram_user_id),),
        )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def get_security_blacklist_entry(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT telegram_user_id, reason, created_at, updated_at
            FROM security_blacklist
            WHERE telegram_user_id = ?
            LIMIT 1
            """,
            (int(telegram_user_id),),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_security_blacklist(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    limit: int = 200,
) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT telegram_user_id, reason, created_at, updated_at
            FROM security_blacklist
            ORDER BY updated_at DESC, telegram_user_id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def count_security_blacklist(get_connection: Callable[[], sqlite3.Connection]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM security_blacklist")
        row = cursor.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def set_security_cooldown(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    last_message_ts: float,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO security_cooldowns (telegram_user_id, last_message_ts, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                last_message_ts = excluded.last_message_ts,
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(telegram_user_id), float(last_message_ts)),
        )
        conn.commit()
    finally:
        conn.close()


def get_security_cooldown(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
) -> float | None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT last_message_ts FROM security_cooldowns WHERE telegram_user_id = ? LIMIT 1",
            (int(telegram_user_id),),
        )
        row = cursor.fetchone()
        return float(row[0]) if row and row[0] is not None else None
    finally:
        conn.close()


def clear_security_cooldowns(get_connection: Callable[[], sqlite3.Connection]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM security_cooldowns")
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def increment_security_suspicious(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO security_suspicious_users (telegram_user_id, strike_count, updated_at)
            VALUES (?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                strike_count = security_suspicious_users.strike_count + 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(telegram_user_id),),
        )
        conn.commit()
        cursor.execute(
            "SELECT strike_count FROM security_suspicious_users WHERE telegram_user_id = ? LIMIT 1",
            (int(telegram_user_id),),
        )
        row = cursor.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def record_security_action_event(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    action_key: str,
    ts_epoch: int,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO security_action_events (telegram_user_id, action_key, ts_epoch)
            VALUES (?, ?, ?)
            """,
            (int(telegram_user_id), str(action_key), int(ts_epoch)),
        )
        conn.commit()
    finally:
        conn.close()


def prune_security_action_events(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    older_than_epoch: int,
    telegram_user_id: int | None = None,
    action_key: str | None = None,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if telegram_user_id is None and action_key is None:
            cursor.execute(
                "DELETE FROM security_action_events WHERE ts_epoch < ?",
                (int(older_than_epoch),),
            )
        elif telegram_user_id is not None and action_key is None:
            cursor.execute(
                "DELETE FROM security_action_events WHERE telegram_user_id = ? AND ts_epoch < ?",
                (int(telegram_user_id), int(older_than_epoch)),
            )
        elif telegram_user_id is None and action_key is not None:
            cursor.execute(
                "DELETE FROM security_action_events WHERE action_key = ? AND ts_epoch < ?",
                (str(action_key), int(older_than_epoch)),
            )
        else:
            cursor.execute(
                """
                DELETE FROM security_action_events
                WHERE telegram_user_id = ? AND action_key = ? AND ts_epoch < ?
                """,
                (int(telegram_user_id), str(action_key), int(older_than_epoch)),
            )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def count_security_action_events_since(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    action_key: str,
    since_epoch: int,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM security_action_events
            WHERE telegram_user_id = ? AND action_key = ? AND ts_epoch > ?
            """,
            (int(telegram_user_id), str(action_key), int(since_epoch)),
        )
        row = cursor.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def record_security_incident(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int | None = None,
    chat_id: int | None = None,
    update_id: int | None = None,
    update_type: str = "",
    action: str,
    reason_code: str,
    severity: str = "warning",
    payload: dict | None = None,
    ts_epoch: int | None = None,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        payload_text = json.dumps(payload or {}, ensure_ascii=False)[:4000]
        cursor.execute(
            """
            INSERT INTO security_incidents (
                telegram_user_id,
                chat_id,
                update_id,
                update_type,
                action,
                reason_code,
                severity,
                payload_json,
                ts_epoch
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(telegram_user_id) if telegram_user_id is not None else None,
                int(chat_id) if chat_id is not None else None,
                int(update_id) if update_id is not None else None,
                str(update_type or ""),
                str(action),
                str(reason_code),
                str(severity or "warning"),
                payload_text,
                int(ts_epoch if ts_epoch is not None else time.time()),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def list_security_incidents(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    limit: int = 100,
    telegram_user_id: int | None = None,
) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if telegram_user_id is None:
            cursor.execute(
                """
                SELECT *
                FROM security_incidents
                ORDER BY ts_epoch DESC, id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM security_incidents
                WHERE telegram_user_id = ?
                ORDER BY ts_epoch DESC, id DESC
                LIMIT ?
                """,
                (int(telegram_user_id), max(1, int(limit))),
            )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def upsert_security_quarantine(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
    status: str,
    reason_code: str,
    strikes: int,
    quarantined_until_epoch: int | None,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO security_quarantine (
                telegram_user_id,
                status,
                reason_code,
                strikes,
                quarantined_until_epoch,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                status = excluded.status,
                reason_code = excluded.reason_code,
                strikes = excluded.strikes,
                quarantined_until_epoch = excluded.quarantined_until_epoch,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(telegram_user_id),
                str(status),
                str(reason_code),
                int(strikes),
                int(quarantined_until_epoch) if quarantined_until_epoch is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_security_quarantine_entry(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT telegram_user_id, status, reason_code, strikes, quarantined_until_epoch, created_at, updated_at
            FROM security_quarantine
            WHERE telegram_user_id = ?
            LIMIT 1
            """,
            (int(telegram_user_id),),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def clear_security_quarantine(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    telegram_user_id: int,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM security_quarantine WHERE telegram_user_id = ?",
            (int(telegram_user_id),),
        )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def count_security_quarantine(get_connection: Callable[[], sqlite3.Connection]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM security_quarantine")
        row = cursor.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def reset_security_suspicious(get_connection: Callable[[], sqlite3.Connection]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM security_suspicious_users")
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def count_security_suspicious_users(get_connection: Callable[[], sqlite3.Connection]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM security_suspicious_users WHERE strike_count > 0")
        row = cursor.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def reset_security_counters(
    get_connection: Callable[[], sqlite3.Connection],
    *,
    clear_blacklist: bool = False,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM security_message_events")
        cursor.execute("DELETE FROM security_action_events")
        cursor.execute("DELETE FROM security_token_usage_daily")
        cursor.execute("DELETE FROM security_cooldowns")
        cursor.execute("DELETE FROM security_suspicious_users")
        cursor.execute("DELETE FROM security_quarantine")
        if clear_blacklist:
            cursor.execute("DELETE FROM security_blacklist")
        conn.commit()
    finally:
        conn.close()
