"""
Работа с SQLite базой данных
"""
from __future__ import annotations

import sqlite3
import logging
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from config import get_config
from lead_perf import log_span_timing, perf_start
import utils
import database_conversations
import database_consent
import database_user_state
import database_leads
import database_reporting
import database_knowledge
import database_security
import database_users
import database_chat_state
config = get_config()

logger = logging.getLogger(__name__)

# ── Column whitelists: only these names are allowed in dynamic SQL ──
_USERS_COLUMNS = frozenset({
    "telegram_id", "username", "first_name", "last_name",
    "consent_given", "consent_date", "consent_revoked", "consent_revoked_at",
    "transborder_consent", "transborder_consent_date",
    "marketing_consent", "marketing_consent_date",
    "conversation_stage", "cta_variant", "cta_shown", "cta_shown_at",
    "offer_profile_override",
    "created_at", "last_interaction",
})

_LEADS_COLUMNS = frozenset({
    "user_id", "name", "email", "phone", "company",
    "team_size", "contracts_per_month", "pain_point", "budget",
    "urgency", "industry", "service_category", "specific_need",
    "temperature", "status", "notes",
    "core_lead_id",
    "conversation_stage", "cta_variant", "cta_shown",
    "lead_magnet_type", "lead_magnet_delivered",
    "notification_sent", "last_message_at",
    "created_at", "updated_at",
})


def _validate_columns(columns, allowed: frozenset, context: str) -> None:
    """Raise ValueError if any column name is not in the whitelist."""
    bad = set(columns) - allowed
    if bad:
        raise ValueError(f"Disallowed column(s) in {context}: {bad}")


class Database:
    """Класс для работы с SQLite базой данных"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Получение подключения к БД"""
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        conn.row_factory = sqlite3.Row  # Доступ к колонкам по имени
        try:
            # Уменьшаем lock-конфликты и удерживаем безопасные ограничения SQLite.
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except Exception as pragma_error:
            logger.debug("SQLite PRAGMA setup skipped: %s", pragma_error)
        return conn

    def _core_get_json(self, path: str, params: dict | None = None):
        if not (config.CORE_API_SYNC_ENABLED and config.CORE_API_URL and config.API_KEY_BOT):
            return None
        started_at = perf_start()

        query = ""
        if params:
            cleaned = {key: value for key, value in params.items() if value is not None}
            if cleaned:
                query = "?" + urllib.parse.urlencode(cleaned)

        request = urllib.request.Request(
            url=f"{config.CORE_API_URL.rstrip('/')}{path}{query}",
            headers={"X-API-Key": config.API_KEY_BOT, "Content-Type": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=config.CORE_API_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
                log_span_timing("lead_db_core_get", started_at, ok=True, path=path)
                return json.loads(raw) if raw else None
        except Exception as error:
            log_span_timing(
                "lead_db_core_get",
                started_at,
                ok=False,
                error=type(error).__name__,
                force=True,
                path=path,
            )
            logger.debug("Core API getter fallback to SQLite for %s: %s", path, error)
            return None

    @staticmethod
    def _map_core_user(row: dict) -> dict:
        return {
            "telegram_id": row.get("telegram_id"),
            "username": row.get("username"),
            "first_name": row.get("first_name"),
            "last_name": row.get("last_name"),
            "email": row.get("email"),
            "name": row.get("name"),
            "consent_given": bool(row.get("consent_given")),
            "consent_date": row.get("consent_date"),
            "consent_revoked": bool(row.get("consent_revoked")),
            "consent_revoked_at": row.get("consent_revoked_at"),
            "transborder_consent": bool(row.get("transborder_consent")),
            "transborder_consent_date": row.get("transborder_consent_date"),
            "marketing_consent": bool(row.get("marketing_consent")),
            "marketing_consent_date": row.get("marketing_consent_date"),
            "conversation_stage": row.get("conversation_stage"),
            "cta_variant": row.get("cta_variant"),
            "cta_shown": bool(row.get("cta_shown")),
            "cta_shown_at": row.get("cta_shown_at"),
            "offer_profile_override": row.get("offer_profile_override"),
            "created_at": row.get("created_at"),
            "last_interaction": row.get("last_interaction"),
        }

    @staticmethod
    def _map_core_lead(row: dict) -> dict:
        return {
            "core_lead_id": row.get("id"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "name": row.get("name"),
            "email": row.get("email"),
            "phone": row.get("phone"),
            "company": row.get("company"),
            "temperature": row.get("temperature"),
            "status": row.get("status"),
            "service_category": row.get("service_category"),
            "specific_need": row.get("specific_need"),
            "pain_point": row.get("pain_point"),
            "budget": row.get("budget"),
            "urgency": row.get("urgency"),
            "industry": row.get("industry"),
            "conversation_stage": row.get("conversation_stage"),
            "cta_variant": row.get("cta_variant"),
            "cta_shown": bool(row.get("cta_shown")),
            "lead_magnet_type": row.get("lead_magnet_type"),
            "lead_magnet_delivered": bool(row.get("lead_magnet_delivered")),
            "notes": row.get("notes"),
        }

    def _merge_user_row_with_core(self, local_user: dict | None) -> dict | None:
        if not local_user:
            return None
        telegram_id = local_user.get("telegram_id")
        if telegram_id is None:
            return local_user
        core_rows = self._core_get_json("/api/v1/users", {"telegram_id": telegram_id, "limit": 1})
        if isinstance(core_rows, list) and core_rows:
            merged = dict(local_user)
            merged.update({k: v for k, v in self._map_core_user(core_rows[0]).items() if v is not None})
            return merged
        return local_user

    def _merge_lead_row_with_core(self, local_lead: dict | None, telegram_user_id: int | None = None) -> dict | None:
        if not local_lead:
            return None
        params = {"source_filter": "telegram_bot", "limit": 1}
        if local_lead.get("id") is not None:
            params["legacy_lead_id"] = local_lead.get("id")
        elif telegram_user_id is not None:
            params["telegram_user_id"] = telegram_user_id
        core_rows = self._core_get_json("/api/v1/leads", params)
        if isinstance(core_rows, list) and core_rows:
            merged = dict(local_lead)
            merged.update({k: v for k, v in self._map_core_lead(core_rows[0]).items() if v is not None})
            return merged
        return local_lead

    def _sync_lead_to_core(self, lead_id: int) -> None:
        """Зеркалирует текущий lead state в core-api, не ломая legacy flow."""
        try:
            from core_api_bridge import core_api_bridge

            if not core_api_bridge.enabled:
                return

            lead = self.get_lead_by_id(lead_id)
            if not lead:
                return

            user = self.get_user_by_id(lead["user_id"]) if lead.get("user_id") else None
            core_lead_id = core_api_bridge.sync_lead(lead, user)
            if core_lead_id and lead.get("core_lead_id") != core_lead_id:
                self.set_core_lead_id(lead_id, core_lead_id)
        except Exception as mirror_error:
            logger.warning("Failed to sync lead %s to core-api: %s", lead_id, mirror_error)

    def _sync_user_to_core(self, user_id: int) -> None:
        """Зеркалирует профиль и согласия пользователя в core-api."""
        try:
            from core_api_bridge import core_api_bridge

            if not core_api_bridge.enabled:
                return

            user = self.get_user_by_id(user_id)
            if not user:
                return

            core_api_bridge.sync_user(user)
        except Exception as mirror_error:
            logger.warning("Failed to sync user %s to core-api: %s", user_id, mirror_error)

    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Таблица users
            cursor.execute("""
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
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")

            # Таблица conversations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_timestamp ON conversations(user_id, timestamp)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_user_role_timestamp "
                "ON conversations(user_id, role, timestamp)"
            )

            # Таблица leads
            cursor.execute("""
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
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_user_id ON leads(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_temperature ON leads(temperature)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at)")

            # Таблица admin_notifications
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id INTEGER NOT NULL,
                    notification_type TEXT NOT NULL,
                    message TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    read_at TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_lead_id ON admin_notifications(lead_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_sent_at ON admin_notifications(sent_at)")
            
            # Таблица analytics_events
            cursor.execute("""
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
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_user_id ON analytics_events(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at ON analytics_events(created_at)")

            # Таблица событий rate-limit (telegram_user_id + unix timestamp).
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

            # Таблица дневного расхода токенов по пользователю.
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

            # Таблица blacklist для долгоживущей блокировки пользователей.
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

            # Таблица cooldown для межсообщенческого антиспама.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS security_cooldowns (
                    telegram_user_id INTEGER PRIMARY KEY,
                    last_message_ts REAL NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Таблица счетчиков подозрительной активности.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS security_suspicious_users (
                    telegram_user_id INTEGER PRIMARY KEY,
                    strike_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Таблица action-событий для callback/non-text антиабуза.
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

            # Таблица security-инцидентов для аудита.
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

            # Таблица карантина пользователей.
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

            # Миграция: добавляем notification_sent если его нет
            cursor.execute("PRAGMA table_info(leads)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'notification_sent' not in columns:
                cursor.execute("ALTER TABLE leads ADD COLUMN notification_sent BOOLEAN DEFAULT 0")
                logger.info("Added notification_sent column to leads table")

            if 'core_lead_id' not in columns:
                cursor.execute("ALTER TABLE leads ADD COLUMN core_lead_id TEXT")
                logger.info("Added core_lead_id column to leads table")
            
            # Миграция: добавляем service_category и specific_need
            if 'service_category' not in columns:
                cursor.execute("ALTER TABLE leads ADD COLUMN service_category TEXT")
                logger.info("Added service_category column to leads table")
            
            if 'specific_need' not in columns:
                cursor.execute("ALTER TABLE leads ADD COLUMN specific_need TEXT")
                logger.info("Added specific_need column to leads table")
            
            # Миграция: добавляем last_message_at для отложенного уведомления
            if 'last_message_at' not in columns:
                cursor.execute("ALTER TABLE leads ADD COLUMN last_message_at TIMESTAMP")
                logger.info("Added last_message_at column to leads table")
            
            if 'conversation_stage' not in columns:
                cursor.execute("ALTER TABLE leads ADD COLUMN conversation_stage TEXT DEFAULT 'discover'")
                logger.info("Added conversation_stage column to leads table")
            
            if 'cta_variant' not in columns:
                cursor.execute("ALTER TABLE leads ADD COLUMN cta_variant TEXT")
                logger.info("Added cta_variant column to leads table")
            
            if 'cta_shown' not in columns:
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

            if 'conversation_stage' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN conversation_stage TEXT DEFAULT 'discover'")
                logger.info("Added conversation_stage column to users table")

            if 'cta_variant' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN cta_variant TEXT")
                logger.info("Added cta_variant column to users table")

            if 'cta_shown' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN cta_shown BOOLEAN DEFAULT 0")
                logger.info("Added cta_shown column to users table")

            if 'cta_shown_at' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN cta_shown_at TIMESTAMP")
                logger.info("Added cta_shown_at column to users table")

            if 'consent_given' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN consent_given BOOLEAN DEFAULT 0")
                logger.info("Added consent_given column to users table")

            if 'consent_date' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN consent_date TIMESTAMP")
                logger.info("Added consent_date column to users table")

            if 'consent_revoked' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN consent_revoked BOOLEAN DEFAULT 0")
                logger.info("Added consent_revoked column to users table")

            if 'consent_revoked_at' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN consent_revoked_at TIMESTAMP")
                logger.info("Added consent_revoked_at column to users table")

            if 'transborder_consent' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN transborder_consent BOOLEAN DEFAULT 0")
                logger.info("Added transborder_consent column to users table")

            if 'transborder_consent_date' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN transborder_consent_date TIMESTAMP")
                logger.info("Added transborder_consent_date column to users table")

            if 'marketing_consent' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN marketing_consent BOOLEAN DEFAULT 0")
                logger.info("Added marketing_consent column to users table")

            if 'marketing_consent_date' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN marketing_consent_date TIMESTAMP")
                logger.info("Added marketing_consent_date column to users table")

            if 'offer_profile_override' not in user_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN offer_profile_override TEXT")
                logger.info("Added offer_profile_override column to users table")

            # Таблица для состояний чатов (вкл/выкл по chat_id)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER UNIQUE NOT NULL,
                    is_enabled BOOLEAN DEFAULT 1,
                    mode TEXT DEFAULT 'bot',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_states_chat_id ON chat_states(chat_id)")
            cursor.execute("PRAGMA table_info(chat_states)")
            chat_state_columns = [column[1] for column in cursor.fetchall()]
            if 'mode' not in chat_state_columns:
                cursor.execute("ALTER TABLE chat_states ADD COLUMN mode TEXT DEFAULT 'bot'")
                logger.info("Added mode column to chat_states table")
            # Таблица для состояний business connection.
            # Нужна, чтобы гарантированно игнорировать апдейты после отключения.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS business_connection_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connection_id TEXT UNIQUE NOT NULL,
                    user_chat_id INTEGER,
                    is_enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_business_connection_states_user_chat_id "
                "ON business_connection_states(user_chat_id)"
            )
            conn.commit()
            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    # === SECURITY ===

    def record_security_message_event(self, telegram_user_id: int, ts_epoch: int) -> None:
        """Сохраняет событие входящего сообщения для персистентного rate-limit."""
        database_security.record_security_message_event(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            ts_epoch=ts_epoch,
        )

    def prune_security_message_events(self, older_than_epoch: int, telegram_user_id: int | None = None) -> int:
        """Удаляет устаревшие события rate-limit, возвращает число удаленных строк."""
        return database_security.prune_security_message_events(
            self.get_connection,
            older_than_epoch=older_than_epoch,
            telegram_user_id=telegram_user_id,
        )

    def count_security_message_events_since(self, telegram_user_id: int, since_epoch: int) -> int:
        """Считает число событий сообщений пользователя после указанного unix-time."""
        return database_security.count_security_message_events_since(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            since_epoch=since_epoch,
        )

    def add_security_tokens_used(self, telegram_user_id: int, date_key: str, tokens: int) -> None:
        """Инкрементирует дневной расход токенов пользователя."""
        database_security.add_security_tokens_used(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            date_key=date_key,
            tokens=tokens,
        )

    def get_security_user_tokens(self, telegram_user_id: int, date_key: str) -> int:
        """Возвращает число токенов пользователя за конкретный день."""
        return database_security.get_security_user_tokens(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            date_key=date_key,
        )

    def get_security_user_tokens_since(self, telegram_user_id: int, start_date_key: str) -> int:
        """Возвращает суммарные токены пользователя с указанной даты (включительно)."""
        return database_security.get_security_user_tokens_since(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            start_date_key=start_date_key,
        )

    def get_security_total_tokens(self, date_key: str) -> int:
        """Возвращает общий расход токенов по всем пользователям за день."""
        return database_security.get_security_total_tokens(
            self.get_connection,
            date_key=date_key,
        )

    def add_security_blacklist(self, telegram_user_id: int, reason: str = "") -> None:
        """Добавляет/обновляет пользователя в персистентном blacklist."""
        database_security.add_security_blacklist(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            reason=reason,
        )

    def remove_security_blacklist(self, telegram_user_id: int) -> int:
        """Удаляет пользователя из blacklist. Возвращает число удаленных строк."""
        return database_security.remove_security_blacklist(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def get_security_blacklist_entry(self, telegram_user_id: int) -> Optional[Dict]:
        """Возвращает запись blacklist по пользователю."""
        return database_security.get_security_blacklist_entry(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def list_security_blacklist(self, limit: int = 200) -> List[Dict]:
        """Список blacklist в порядке свежих изменений."""
        return database_security.list_security_blacklist(
            self.get_connection,
            limit=limit,
        )

    def count_security_blacklist(self) -> int:
        """Количество пользователей в blacklist."""
        return database_security.count_security_blacklist(self.get_connection)

    def set_security_cooldown(self, telegram_user_id: int, last_message_ts: float) -> None:
        """Сохраняет отметку последнего сообщения пользователя для cooldown."""
        database_security.set_security_cooldown(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            last_message_ts=last_message_ts,
        )

    def get_security_cooldown(self, telegram_user_id: int) -> Optional[float]:
        """Возвращает ts последнего сообщения пользователя для cooldown."""
        return database_security.get_security_cooldown(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def clear_security_cooldowns(self) -> int:
        """Очищает все cooldown-записи."""
        return database_security.clear_security_cooldowns(self.get_connection)

    def increment_security_suspicious(self, telegram_user_id: int) -> int:
        """Увеличивает счетчик suspicious strike и возвращает новое значение."""
        return database_security.increment_security_suspicious(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def record_security_action_event(self, telegram_user_id: int, action_key: str, ts_epoch: int) -> None:
        """Сохраняет action-событие для callback/non-text антиабуза."""
        database_security.record_security_action_event(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            action_key=action_key,
            ts_epoch=ts_epoch,
        )

    def prune_security_action_events(
        self,
        older_than_epoch: int,
        telegram_user_id: int | None = None,
        action_key: str | None = None,
    ) -> int:
        """Удаляет устаревшие action-события."""
        return database_security.prune_security_action_events(
            self.get_connection,
            older_than_epoch=older_than_epoch,
            telegram_user_id=telegram_user_id,
            action_key=action_key,
        )

    def count_security_action_events_since(self, telegram_user_id: int, action_key: str, since_epoch: int) -> int:
        """Считает action-события пользователя по ключу за окно."""
        return database_security.count_security_action_events_since(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            action_key=action_key,
            since_epoch=since_epoch,
        )

    def record_security_incident(
        self,
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
        """Сохраняет security-инцидент для аудита."""
        return database_security.record_security_incident(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            update_id=update_id,
            update_type=update_type,
            action=action,
            reason_code=reason_code,
            severity=severity,
            payload=payload,
            ts_epoch=ts_epoch,
        )

    def list_security_incidents(self, limit: int = 100, telegram_user_id: int | None = None) -> List[Dict]:
        """Возвращает свежие security-инциденты."""
        return database_security.list_security_incidents(
            self.get_connection,
            limit=limit,
            telegram_user_id=telegram_user_id,
        )

    def upsert_security_quarantine(
        self,
        telegram_user_id: int,
        *,
        status: str,
        reason_code: str,
        strikes: int,
        quarantined_until_epoch: int | None,
    ) -> None:
        """Создает или обновляет карантин пользователя."""
        database_security.upsert_security_quarantine(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            status=status,
            reason_code=reason_code,
            strikes=strikes,
            quarantined_until_epoch=quarantined_until_epoch,
        )

    def get_security_quarantine_entry(self, telegram_user_id: int) -> Optional[Dict]:
        """Возвращает запись карантина пользователя."""
        return database_security.get_security_quarantine_entry(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def clear_security_quarantine(self, telegram_user_id: int) -> int:
        """Снимает карантин с пользователя."""
        return database_security.clear_security_quarantine(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def count_security_quarantine(self) -> int:
        """Количество пользователей в активном карантине."""
        return database_security.count_security_quarantine(self.get_connection)

    def reset_security_suspicious(self) -> int:
        """Очищает счетчик suspicious пользователей."""
        return database_security.reset_security_suspicious(self.get_connection)

    def count_security_suspicious_users(self) -> int:
        """Количество пользователей с хотя бы одним suspicious strike."""
        return database_security.count_security_suspicious_users(self.get_connection)

    def reset_security_counters(self, clear_blacklist: bool = False) -> None:
        """Сбрасывает персистентные security-счетчики."""
        database_security.reset_security_counters(
            self.get_connection,
            clear_blacklist=clear_blacklist,
        )

    # === USERS ===

    # === BUSINESS / CHAT STATES ===

    def is_chat_enabled(self, chat_id: int) -> bool:
        """Проверка, включен ли чат для автоответов."""
        return database_chat_state.is_chat_enabled(
            self.get_connection,
            chat_id=chat_id,
        )

    def set_chat_enabled(self, chat_id: int, enabled: bool):
        """Включение/отключение автоответов в конкретном чате."""
        database_chat_state.set_chat_enabled(
            self.get_connection,
            chat_id=chat_id,
            enabled=enabled,
        )

    def get_chat_mode(self, chat_id: int) -> str:
        """Режим чата: bot | personal."""
        return database_chat_state.get_chat_mode(
            self.get_connection,
            chat_id=chat_id,
        )

    def set_chat_mode(self, chat_id: int, mode: str) -> None:
        """Устанавливает режим чата."""
        database_chat_state.set_chat_mode(
            self.get_connection,
            chat_id=chat_id,
            mode=mode,
        )

    def get_disabled_chats(self) -> list:
        """Получение списка отключенных чатов."""
        return database_chat_state.get_disabled_chats(self.get_connection)

    def set_business_connection_state(self, connection_id: str, user_chat_id: Optional[int], is_enabled: bool):
        """Сохраняет состояние business connection (вкл/выкл)."""
        database_chat_state.set_business_connection_state(
            self.get_connection,
            connection_id=connection_id,
            user_chat_id=user_chat_id,
            is_enabled=is_enabled,
        )

    def is_business_connection_enabled(self, connection_id: Optional[str]) -> bool:
        """
        Проверяет включена ли business connection.
        Если состояние неизвестно, не блокируем (True по умолчанию).
        """
        return database_chat_state.is_business_connection_enabled(
            self.get_connection,
            connection_id=connection_id,
        )

    def create_or_update_user(self, telegram_id: int, username: str = None,
                              first_name: str = None, last_name: str = None) -> int:
        """Создание или обновление пользователя"""
        return database_users.create_or_update_user(
            self.get_connection,
            self._sync_user_to_core,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

    def get_local_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Возвращает локальную запись пользователя без merge с core-api."""
        return database_users.get_local_user_by_telegram_id(
            self.get_connection,
            telegram_id=telegram_id,
        )

    def get_local_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Возвращает локальную запись пользователя без merge с core-api."""
        return database_users.get_local_user_by_id(
            self.get_connection,
            user_id=user_id,
        )

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Получение пользователя по telegram_id"""
        user = self.get_local_user_by_telegram_id(telegram_id)
        if user:
            return self._merge_user_row_with_core(user)
        return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Получение пользователя по user_id"""
        user = self.get_local_user_by_id(user_id)
        if user:
            return self._merge_user_row_with_core(user)
        return None

    def get_user_offer_profile(self, user_id: int) -> Optional[str]:
        """Возвращает ручной override профиля предложений пользователя."""
        return database_users.get_user_offer_profile(
            self.get_local_user_by_id,
            user_id=user_id,
        )

    def set_user_offer_profile(self, user_id: int, profile_key: Optional[str]) -> None:
        """Сохраняет ручной override профиля предложений (или сбрасывает в авто-режим)."""
        database_users.set_user_offer_profile(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
            profile_key=profile_key,
        )

    def get_recent_users(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Получение последних активных пользователей."""
        return database_users.get_recent_users(
            self.get_connection,
            limit=limit,
            offset=offset,
        )

    def count_users(self) -> int:
        """Возвращает общее число пользователей в локальной БД."""
        return database_users.count_users(self.get_connection)

    def get_users_without_consent(self, limit: int = 20) -> List[Dict]:
        """Пользователи без активного согласия на обработку ПД."""
        return database_users.get_users_without_consent(
            self.get_connection,
            limit=limit,
        )

    def get_users_with_revoked_consent(self, limit: int = 20) -> List[Dict]:
        """Пользователи, которые отозвали согласие."""
        return database_users.get_users_with_revoked_consent(
            self.get_connection,
            limit=limit,
        )

    def get_user_consent_state(self, user_id: int) -> Dict:
        """Получение статуса согласий пользователя."""
        return database_consent.get_user_consent_state(
            self.get_local_user_by_id,
            user_id=user_id,
        )

    def grant_user_consent(self, user_id: int) -> None:
        """Выдать согласие на обработку ПД."""
        database_consent.grant_user_consent(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
        )

    def set_user_transborder_consent(self, user_id: int, granted: bool) -> None:
        """Обновить согласие на трансграничную передачу."""
        database_consent.set_user_transborder_consent(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
            granted=granted,
        )

    def set_user_marketing_consent(self, user_id: int, granted: bool) -> None:
        """Обновить согласие на рассылки."""
        database_consent.set_user_marketing_consent(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
            granted=granted,
        )

    def revoke_user_consent_and_delete_data(self, user_id: int) -> Dict:
        """
        Отзыв согласий + анонимизация ПД в анкете + удаление истории диалога.
        Возвращает сводку по измененным записям.
        """
        return database_consent.revoke_user_consent_and_delete_data(
            self.get_connection,
            self._sync_user_to_core,
            self._sync_lead_to_core,
            user_id=user_id,
        )

    def reset_user_to_new_state(self, user_id: int) -> Dict:
        """
        Сброс пользователя в состояние "как новый":
        - удаляются диалоги, лиды и аналитика;
        - обнуляются согласия и состояние воронки;
        - профиль пользователя (telegram_id/username/имя) сохраняется.
        """
        return database_user_state.reset_user_to_new_state(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
        )

    def delete_user_completely(self, user_id: int) -> Dict:
        """
        Полное удаление пользователя и всех связанных данных.
        """
        return database_user_state.delete_user_completely(
            self.get_connection,
            user_id=user_id,
        )

    def export_user_data(self, user_id: int) -> Dict:
        """Экспорт данных пользователя и связанной анкеты."""
        return database_consent.export_user_data(
            self.get_user_by_id,
            self.get_lead_by_user_id,
            user_id=user_id,
        )

    def update_user_fields(self, user_id: int, fields: Dict[str, str]) -> bool:
        """Обновление полей профиля пользователя."""
        return database_user_state.update_user_fields(
            self.get_connection,
            self._sync_user_to_core,
            _validate_columns,
            _USERS_COLUMNS,
            user_id=user_id,
            fields=fields,
        )
    
    def get_user_funnel_state(self, user_id: int) -> Dict:
        """
        Получение состояния воронки пользователя.

        Returns:
            dict: conversation_stage, cta_variant, cta_shown, cta_shown_at
        """
        return database_user_state.get_user_funnel_state(
            self.get_connection,
            user_id=user_id,
        )

    def update_user_funnel_state(
        self,
        user_id: int,
        conversation_stage: str = None,
        cta_variant: str = None,
        cta_shown: Optional[bool] = None,
    ) -> None:
        """Обновление состояния воронки пользователя."""
        database_user_state.update_user_funnel_state(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
            conversation_stage=conversation_stage,
            cta_variant=cta_variant,
            cta_shown=cta_shown,
        )

    def reset_user_funnel_state(self, user_id: int) -> None:
        """Сброс воронки при /reset."""
        database_user_state.reset_user_funnel_state(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
        )

    def update_lead_funnel_state(
        self,
        user_id: int,
        conversation_stage: str = None,
        cta_variant: str = None,
        cta_shown: Optional[bool] = None,
    ) -> None:
        """Синхронизация состояния воронки в таблице leads для последнего лида пользователя."""
        database_leads.update_lead_funnel_state(
            self.get_connection,
            user_id=user_id,
            conversation_stage=conversation_stage,
            cta_variant=cta_variant,
            cta_shown=cta_shown,
        )

    def update_lead_funnel_state_by_id(
        self,
        lead_id: int,
        conversation_stage: str = None,
        cta_variant: str = None,
        cta_shown: Optional[bool] = None,
    ) -> None:
        """Синхронизация состояния воронки для конкретного лида."""
        database_leads.update_lead_funnel_state_by_id(
            self.get_connection,
            lead_id=lead_id,
            conversation_stage=conversation_stage,
            cta_variant=cta_variant,
            cta_shown=cta_shown,
        )

    def track_event(
        self,
        user_id: int,
        event_type: str,
        payload: Optional[Dict] = None,
        lead_id: Optional[int] = None,
    ) -> int:
        """Запись события аналитики."""
        return database_reporting.track_event(
            self.get_connection,
            self.get_lead_by_id,
            user_id=user_id,
            event_type=event_type,
            payload=payload,
            lead_id=lead_id,
        )

    # === CONVERSATIONS ===

    def add_message(self, user_id: int, role: str, message: str):
        """Добавление сообщения в историю диалога"""
        database_conversations.add_message(
            self.get_connection,
            user_id=user_id,
            role=role,
            message=message,
        )

    def get_conversation_history(self, user_id: int, limit: int = None) -> List[Dict]:
        """Получение истории диалога"""
        effective_limit = limit or config.MAX_HISTORY_MESSAGES
        return database_conversations.get_conversation_history(
            self.get_connection,
            user_id=user_id,
            limit=effective_limit,
        )

    def clear_conversation_history(self, user_id: int):
        """Очистка истории диалога"""
        database_conversations.clear_conversation_history(
            self.get_connection,
            user_id=user_id,
        )

    def cleanup_conversations_by_retention(self, retention_days: int | None = None) -> int:
        """Удаляет сообщения диалогов старше заданного retention-порога."""
        days = max(1, int(retention_days or config.CONVERSATION_RETENTION_DAYS))
        return database_conversations.cleanup_conversations_by_retention(
            self.get_connection,
            retention_days=days,
        )

    # === LEADS ===

    def create_or_update_lead(self, user_id: int, lead_data: Dict) -> int:
        """Создание или обновление лида"""
        return database_leads.create_or_update_lead(
            self.get_connection,
            self._sync_lead_to_core,
            _LEADS_COLUMNS,
            user_id=user_id,
            lead_data=lead_data,
        )

    def create_new_lead(self, user_id: int, lead_data: Dict) -> int:
        """Принудительное создание нового лида, без merge с предыдущим."""
        return database_leads.create_new_lead(
            self.get_connection,
            self._sync_lead_to_core,
            _LEADS_COLUMNS,
            user_id=user_id,
            lead_data=lead_data,
        )

    def get_lead_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Получение последнего лида по user_id"""
        return database_leads.get_lead_by_user_id(
            self.get_connection,
            self.get_local_user_by_id,
            self._merge_lead_row_with_core,
            user_id=user_id,
        )

    def get_local_lead_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Получение последнего лида по user_id без merge с core-api."""
        return database_leads.get_local_lead_by_user_id(
            self.get_connection,
            user_id=user_id,
        )

    def mark_lead_notification_sent(self, lead_id: int):
        """Помечаем что уведомление о лиде отправлено"""
        database_leads.mark_lead_notification_sent(
            self.get_connection,
            lead_id=lead_id,
        )

    def get_lead_by_id(self, lead_id: int) -> Optional[Dict]:
        """Получение лида по lead_id"""
        return database_leads.get_lead_by_id(
            self.get_connection,
            self.get_user_by_id,
            self._merge_lead_row_with_core,
            lead_id=lead_id,
        )

    def set_core_lead_id(self, lead_id: int, core_lead_id: str) -> None:
        """Сохраняет UUID лида из core-api для legacy лида."""
        database_leads.set_core_lead_id(
            self.get_connection,
            lead_id=lead_id,
            core_lead_id=core_lead_id,
        )

    def get_all_leads(
        self,
        temperature: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Получение всех лидов с фильтрами"""
        return database_leads.get_all_leads(
            self.get_connection,
            temperature=temperature,
            status=status,
            limit=limit,
            offset=offset,
        )
    
    def get_leads_ready_for_notification(self, idle_minutes: int = 5) -> List[Dict]:
        """
        Получение лидов готовых к уведомлению:
        - Прошло idle_minutes минут с последнего сообщения
        - Уведомление еще не отправлено
        - Лид теплый или горячий (или есть ключевые данные)
        """
        return database_leads.get_leads_ready_for_notification(
            self.get_connection,
            idle_minutes=idle_minutes,
        )
    
    def update_lead_last_message_time(self, user_id: int):
        """Обновление времени последнего сообщения лида"""
        database_leads.update_lead_last_message_time(
            self.get_connection,
            user_id=user_id,
        )
    
    # === KNOWLEDGE BASE / RAG ===
    
    def get_successful_conversations(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        Получение успешных диалогов (warm/hot лиды) для RAG
        
        Returns:
            Список словарей с полными диалогами и метаданными лидов
        """
        return database_knowledge.get_successful_conversations(
            self.get_connection,
            limit=limit,
            offset=offset,
        )
    
    def get_conversations_by_category(
        self, 
        service_category: str, 
        temperature: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Получение диалогов по категории услуги
        
        Args:
            service_category: Категория услуги
            temperature: Фильтр по температуре (опционально)
            limit: Максимальное количество результатов
            
        Returns:
            Список диалогов с метаданными
        """
        return database_knowledge.get_conversations_by_category(
            self.get_connection,
            service_category=service_category,
            temperature=temperature,
            limit=limit,
        )

    # === ADMIN NOTIFICATIONS ===

    def create_notification(self, lead_id: int, notification_type: str,
                            message: str) -> int:
        """Создание уведомления для админа"""
        return database_leads.create_notification(
            self.get_connection,
            lead_id=lead_id,
            notification_type=notification_type,
            message=message,
        )

    # === STATISTICS ===

    def get_statistics(self, days: int = 30) -> Dict:
        """Получение статистики"""
        return database_reporting.get_statistics(
            self.get_connection,
            days=days,
        )

    def get_funnel_report(self, days: int = 30) -> Dict:
        """
        SQL-отчет по этапам воронки за период.
        Основан на событиях analytics_events и активности в conversations.
        """
        return database_reporting.get_funnel_report(
            self.get_connection,
            days=days,
        )

    def get_ab_cta_report(self, days: int = 30) -> Dict:
        """
        SQL-отчет по A/B вариантам CTA за период.
        """
        return database_reporting.get_ab_cta_report(
            self.get_connection,
            days=days,
        )


# Создание глобального экземпляра базы данных
db = Database()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    print("Initializing database...")
    Database()
    print("Database initialized successfully!")
