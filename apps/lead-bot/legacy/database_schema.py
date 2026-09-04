"""
SQLite schema initialization and migrations for the legacy lead-bot database.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable


def init_database(get_connection: Callable[[], sqlite3.Connection], logger: logging.Logger) -> None:
    """Create schema objects and apply legacy additive migrations."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                consent_given BOOLEAN DEFAULT 0,
                consent_date TIMESTAMP,
                consent_revoked BOOLEAN DEFAULT 0,
                consent_revoked_at TIMESTAMP,
                transborder_consent BOOLEAN DEFAULT 0,
                transborder_consent_date TIMESTAMP,
                marketing_consent BOOLEAN DEFAULT 0,
                marketing_consent_date TIMESTAMP,
                conversation_stage TEXT DEFAULT 'discover',
                cta_variant TEXT,
                cta_shown BOOLEAN DEFAULT 0,
                cta_shown_at TIMESTAMP,
                offer_profile_override TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_timestamp ON conversations(user_id, timestamp)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_role_timestamp "
            "ON conversations(user_id, role, timestamp)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT,
                email TEXT,
                phone TEXT,
                company TEXT,
                team_size TEXT,
                contracts_per_month TEXT,
                pain_point TEXT,
                budget TEXT,
                urgency TEXT,
                industry TEXT,
                service_category TEXT,
                specific_need TEXT,
                temperature TEXT DEFAULT 'cold',
                status TEXT DEFAULT 'new',
                notes TEXT,
                core_lead_id TEXT,
                conversation_stage TEXT DEFAULT 'discover',
                cta_variant TEXT,
                cta_shown BOOLEAN DEFAULT 0,
                lead_magnet_type TEXT,
                lead_magnet_delivered BOOLEAN DEFAULT 0,
                notification_sent BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_user_id ON leads(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_temperature ON leads(temperature)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at)")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                notification_type TEXT NOT NULL,
                message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_lead_id ON admin_notifications(lead_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_sent_at ON admin_notifications(sent_at)")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                lead_id INTEGER,
                event_type TEXT NOT NULL,
                event_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_user_id ON analytics_events(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at ON analytics_events(created_at)")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS security_message_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                ts_epoch INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_security_message_events_user_ts "
            "ON security_message_events(telegram_user_id, ts_epoch)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_security_message_events_ts "
            "ON security_message_events(ts_epoch)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS security_token_usage_daily (
                telegram_user_id INTEGER NOT NULL,
                date_key TEXT NOT NULL,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (telegram_user_id, date_key)
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_security_token_usage_daily_date "
            "ON security_token_usage_daily(date_key)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS security_blacklist (
                telegram_user_id INTEGER PRIMARY KEY,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS security_cooldowns (
                telegram_user_id INTEGER PRIMARY KEY,
                last_message_ts REAL NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS security_suspicious_users (
                telegram_user_id INTEGER PRIMARY KEY,
                strike_count INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS security_action_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                action_key TEXT NOT NULL,
                ts_epoch INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_security_action_events_user_key_ts "
            "ON security_action_events(telegram_user_id, action_key, ts_epoch)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_security_action_events_ts "
            "ON security_action_events(ts_epoch)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS security_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER,
                chat_id INTEGER,
                update_id INTEGER,
                update_type TEXT,
                action TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'warning',
                payload_json TEXT,
                ts_epoch INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_security_incidents_user_ts "
            "ON security_incidents(telegram_user_id, ts_epoch DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_security_incidents_reason_ts "
            "ON security_incidents(reason_code, ts_epoch DESC)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS security_quarantine (
                telegram_user_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'active',
                reason_code TEXT NOT NULL,
                strikes INTEGER NOT NULL DEFAULT 1,
                quarantined_until_epoch INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Состояние уточняющего диалога по юридическому обращению.
        #
        # Хранится в базе, а не в памяти процесса: диалог идёт минутами, а
        # деплой может случиться в любой момент. Потеря состояния означала бы,
        # что клиент отвечает на вопрос, а бот отвечает ему из общей воронки —
        # для человека это выглядит так, будто его перестали слушать.
        #
        # Здесь только ход разговора. Содержательное — ответы, документы,
        # подпись — уходит в core-api сразу и от этой таблицы не зависит.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS intake_dialog_state (
                telegram_user_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute("PRAGMA table_info(leads)")
        columns = [column[1] for column in cursor.fetchall()]

        if "notification_sent" not in columns:
            cursor.execute("ALTER TABLE leads ADD COLUMN notification_sent BOOLEAN DEFAULT 0")
            logger.info("Added notification_sent column to leads table")

        if "core_lead_id" not in columns:
            cursor.execute("ALTER TABLE leads ADD COLUMN core_lead_id TEXT")
            logger.info("Added core_lead_id column to leads table")

        if "service_category" not in columns:
            cursor.execute("ALTER TABLE leads ADD COLUMN service_category TEXT")
            logger.info("Added service_category column to leads table")

        if "specific_need" not in columns:
            cursor.execute("ALTER TABLE leads ADD COLUMN specific_need TEXT")
            logger.info("Added specific_need column to leads table")

        if "last_message_at" not in columns:
            cursor.execute("ALTER TABLE leads ADD COLUMN last_message_at TIMESTAMP")
            logger.info("Added last_message_at column to leads table")

        if "conversation_stage" not in columns:
            cursor.execute("ALTER TABLE leads ADD COLUMN conversation_stage TEXT DEFAULT 'discover'")
            logger.info("Added conversation_stage column to leads table")

        if "cta_variant" not in columns:
            cursor.execute("ALTER TABLE leads ADD COLUMN cta_variant TEXT")
            logger.info("Added cta_variant column to leads table")

        if "cta_shown" not in columns:
            cursor.execute("ALTER TABLE leads ADD COLUMN cta_shown BOOLEAN DEFAULT 0")
            logger.info("Added cta_shown column to leads table")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_user_created_at ON leads(user_id, created_at DESC)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_notification_last_message "
            "ON leads(notification_sent, last_message_at)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_core_lead_id ON leads(core_lead_id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_status_created_at "
            "ON leads(status, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_temperature_created_at "
            "ON leads(temperature, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_service_category_created_at "
            "ON leads(service_category, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_notify_temp_last_message "
            "ON leads(notification_sent, temperature, last_message_at)"
        )

        cursor.execute("PRAGMA table_info(users)")
        user_columns = [column[1] for column in cursor.fetchall()]

        if "conversation_stage" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN conversation_stage TEXT DEFAULT 'discover'")
            logger.info("Added conversation_stage column to users table")

        if "cta_variant" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN cta_variant TEXT")
            logger.info("Added cta_variant column to users table")

        if "cta_shown" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN cta_shown BOOLEAN DEFAULT 0")
            logger.info("Added cta_shown column to users table")

        if "cta_shown_at" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN cta_shown_at TIMESTAMP")
            logger.info("Added cta_shown_at column to users table")

        if "consent_given" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN consent_given BOOLEAN DEFAULT 0")
            logger.info("Added consent_given column to users table")

        if "consent_date" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN consent_date TIMESTAMP")
            logger.info("Added consent_date column to users table")

        if "consent_revoked" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN consent_revoked BOOLEAN DEFAULT 0")
            logger.info("Added consent_revoked column to users table")

        if "consent_revoked_at" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN consent_revoked_at TIMESTAMP")
            logger.info("Added consent_revoked_at column to users table")

        if "transborder_consent" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN transborder_consent BOOLEAN DEFAULT 0")
            logger.info("Added transborder_consent column to users table")

        if "transborder_consent_date" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN transborder_consent_date TIMESTAMP")
            logger.info("Added transborder_consent_date column to users table")

        if "marketing_consent" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN marketing_consent BOOLEAN DEFAULT 0")
            logger.info("Added marketing_consent column to users table")

        if "marketing_consent_date" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN marketing_consent_date TIMESTAMP")
            logger.info("Added marketing_consent_date column to users table")

        if "offer_profile_override" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN offer_profile_override TEXT")
            logger.info("Added offer_profile_override column to users table")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE NOT NULL,
                is_enabled BOOLEAN DEFAULT 1,
                mode TEXT DEFAULT 'bot',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_states_chat_id ON chat_states(chat_id)")
        cursor.execute("PRAGMA table_info(chat_states)")
        chat_state_columns = [column[1] for column in cursor.fetchall()]
        if "mode" not in chat_state_columns:
            cursor.execute("ALTER TABLE chat_states ADD COLUMN mode TEXT DEFAULT 'bot'")
            logger.info("Added mode column to chat_states table")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS business_connection_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_id TEXT UNIQUE NOT NULL,
                user_chat_id INTEGER,
                is_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_business_connection_states_user_chat_id "
            "ON business_connection_states(user_chat_id)"
        )

        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as error:
        logger.error("Error initializing database: %s", error)
        conn.rollback()
        raise
    finally:
        conn.close()
