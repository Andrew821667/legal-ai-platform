"""
Работа с SQLite базой данных
"""
import sqlite3
import logging
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from config import Config
config = Config()

logger = logging.getLogger(__name__)

# ── Column whitelists: only these names are allowed in dynamic SQL ──
_USERS_COLUMNS = frozenset({
    "telegram_id", "username", "first_name", "last_name",
    "consent_given", "consent_date", "consent_revoked", "consent_revoked_at",
    "transborder_consent", "transborder_consent_date",
    "marketing_consent", "marketing_consent_date",
    "conversation_stage", "cta_variant", "cta_shown", "cta_shown_at",
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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Доступ к колонкам по имени
        return conn

    def _core_get_json(self, path: str, params: dict | None = None):
        if not (config.CORE_API_SYNC_ENABLED and config.CORE_API_URL and config.API_KEY_BOT):
            return None

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
                return json.loads(raw) if raw else None
        except Exception as error:
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

    # === USERS ===

    # === BUSINESS / CHAT STATES ===

    def is_chat_enabled(self, chat_id: int) -> bool:
        """Проверка, включен ли чат для автоответов."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT is_enabled FROM chat_states WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()
            return bool(row[0]) if row else True
        finally:
            conn.close()

    def set_chat_enabled(self, chat_id: int, enabled: bool):
        """Включение/отключение автоответов в конкретном чате."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO chat_states (chat_id, is_enabled, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    is_enabled = excluded.is_enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (chat_id, 1 if enabled else 0),
            )
            conn.commit()
            logger.info("Chat %s %s", chat_id, "enabled" if enabled else "disabled")
        except Exception as e:
            logger.error(f"Error setting chat enabled state: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_chat_mode(self, chat_id: int) -> str:
        """Режим чата: bot | personal."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT mode FROM chat_states WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()
            mode = (row[0] if row and row[0] else "bot").strip().lower()
            return mode if mode in {"bot", "personal"} else "bot"
        finally:
            conn.close()

    def set_chat_mode(self, chat_id: int, mode: str) -> None:
        """Устанавливает режим чата."""
        normalized_mode = (mode or "bot").strip().lower()
        if normalized_mode not in {"bot", "personal"}:
            normalized_mode = "bot"

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO chat_states (chat_id, is_enabled, mode, updated_at)
                VALUES (?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    mode = excluded.mode,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (chat_id, normalized_mode),
            )
            conn.commit()
            logger.info("Chat %s switched to mode=%s", chat_id, normalized_mode)
        except Exception as e:
            logger.error(f"Error setting chat mode: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_disabled_chats(self) -> list:
        """Получение списка отключенных чатов."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT chat_id FROM chat_states WHERE is_enabled = 0")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def set_business_connection_state(self, connection_id: str, user_chat_id: Optional[int], is_enabled: bool):
        """Сохраняет состояние business connection (вкл/выкл)."""
        if not connection_id:
            return
        connection_key = str(connection_id)

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO business_connection_states (connection_id, user_chat_id, is_enabled, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(connection_id) DO UPDATE SET
                    user_chat_id = excluded.user_chat_id,
                    is_enabled = excluded.is_enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (connection_key, user_chat_id, 1 if is_enabled else 0),
            )
            conn.commit()
            logger.info(
                "Business connection %s for user_chat_id=%s set to %s",
                connection_key,
                user_chat_id,
                "enabled" if is_enabled else "disabled",
            )
        except Exception as e:
            logger.error(f"Error setting business connection state: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def is_business_connection_enabled(self, connection_id: Optional[str]) -> bool:
        """
        Проверяет включена ли business connection.
        Если состояние неизвестно, не блокируем (True по умолчанию).
        """
        if not connection_id:
            return True
        connection_key = str(connection_id)

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT is_enabled FROM business_connection_states WHERE connection_id = ?",
                (connection_key,),
            )
            row = cursor.fetchone()
            return bool(row[0]) if row else True
        finally:
            conn.close()

    def create_or_update_user(self, telegram_id: int, username: str = None,
                              first_name: str = None, last_name: str = None) -> int:
        """Создание или обновление пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    last_interaction = CURRENT_TIMESTAMP
            """, (telegram_id, username, first_name, last_name))

            conn.commit()

            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
            user_id = cursor.fetchone()[0]

            logger.info(f"User {telegram_id} created/updated with id {user_id}")
            self._sync_user_to_core(user_id)
            return user_id

        except Exception as e:
            logger.error(f"Error creating/updating user: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Получение пользователя по telegram_id"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()

            if row:
                return self._merge_user_row_with_core(dict(row))
            return None

        finally:
            conn.close()
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Получение пользователя по user_id"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()

            if row:
                return self._merge_user_row_with_core(dict(row))
            return None

        finally:
            conn.close()

    def get_recent_users(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Получение последних активных пользователей."""
        conn = self.get_connection()
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
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def count_users(self) -> int:
        """Возвращает общее число пользователей в локальной БД."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            row = cursor.fetchone()
            return int(row[0] if row else 0)
        finally:
            conn.close()

    def get_users_without_consent(self, limit: int = 20) -> List[Dict]:
        """Пользователи без активного согласия на обработку ПД."""
        conn = self.get_connection()
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
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_users_with_revoked_consent(self, limit: int = 20) -> List[Dict]:
        """Пользователи, которые отозвали согласие."""
        conn = self.get_connection()
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
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_user_consent_state(self, user_id: int) -> Dict:
        """Получение статуса согласий пользователя."""
        user = self.get_user_by_id(user_id)
        if not user:
            return {}
        return {
            "consent_given": user.get("consent_given"),
            "consent_date": user.get("consent_date"),
            "consent_revoked": user.get("consent_revoked"),
            "consent_revoked_at": user.get("consent_revoked_at"),
            "transborder_consent": user.get("transborder_consent"),
            "transborder_consent_date": user.get("transborder_consent_date"),
            "marketing_consent": user.get("marketing_consent"),
            "marketing_consent_date": user.get("marketing_consent_date"),
        }

    def grant_user_consent(self, user_id: int) -> None:
        """Выдать согласие на обработку ПД."""
        conn = self.get_connection()
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
            self._sync_user_to_core(user_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def set_user_transborder_consent(self, user_id: int, granted: bool) -> None:
        """Обновить согласие на трансграничную передачу."""
        conn = self.get_connection()
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
            self._sync_user_to_core(user_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def set_user_marketing_consent(self, user_id: int, granted: bool) -> None:
        """Обновить согласие на рассылки."""
        conn = self.get_connection()
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
            self._sync_user_to_core(user_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def revoke_user_consent_and_delete_data(self, user_id: int) -> Dict:
        """
        Отзыв согласий + анонимизация ПД в анкете + удаление истории диалога.
        Возвращает сводку по измененным записям.
        """
        conn = self.get_connection()
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
            self._sync_user_to_core(user_id)
            for lead_id in affected_lead_ids:
                self._sync_lead_to_core(int(lead_id))
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

    def reset_user_to_new_state(self, user_id: int) -> Dict:
        """
        Сброс пользователя в состояние "как новый":
        - удаляются диалоги, лиды и аналитика;
        - обнуляются согласия и состояние воронки;
        - профиль пользователя (telegram_id/username/имя) сохраняется.
        """
        conn = self.get_connection()
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
            self._sync_user_to_core(user_id)
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

    def delete_user_completely(self, user_id: int) -> Dict:
        """
        Полное удаление пользователя и всех связанных данных.
        """
        conn = self.get_connection()
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

    def export_user_data(self, user_id: int) -> Dict:
        """Экспорт данных пользователя и связанной анкеты."""
        user = self.get_user_by_id(user_id)
        if not user:
            return {}

        lead = self.get_lead_by_user_id(user_id)
        return {
            "user": user,
            "lead": lead or {},
            "consent": {
                "consent_given": bool(user.get("consent_given")),
                "consent_date": user.get("consent_date"),
                "consent_revoked": bool(user.get("consent_revoked")),
                "consent_revoked_at": user.get("consent_revoked_at"),
                "transborder_consent": bool(user.get("transborder_consent")),
                "transborder_consent_date": user.get("transborder_consent_date"),
                "marketing_consent": bool(user.get("marketing_consent")),
                "marketing_consent_date": user.get("marketing_consent_date"),
            },
        }

    def update_user_fields(self, user_id: int, fields: Dict[str, str]) -> bool:
        """Обновление полей профиля пользователя."""
        if not fields:
            return False
        _validate_columns(fields.keys(), _USERS_COLUMNS, "update_user_fields")
        conn = self.get_connection()
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
                self._sync_user_to_core(user_id)
            return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_user_funnel_state(self, user_id: int) -> Dict:
        """
        Получение состояния воронки пользователя.

        Returns:
            dict: conversation_stage, cta_variant, cta_shown, cta_shown_at
        """
        conn = self.get_connection()
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
        self,
        user_id: int,
        conversation_stage: str = None,
        cta_variant: str = None,
        cta_shown: Optional[bool] = None,
    ) -> None:
        """Обновление состояния воронки пользователя."""
        updates = []
        values: List = []

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

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            values.append(user_id)
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                values,
            )
            conn.commit()
            self._sync_user_to_core(user_id)
        except Exception as e:
            logger.error(f"Error updating user funnel state: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def reset_user_funnel_state(self, user_id: int) -> None:
        """Сброс воронки при /reset."""
        conn = self.get_connection()
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
            self._sync_user_to_core(user_id)
        except Exception as e:
            logger.error(f"Error resetting user funnel state: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_lead_funnel_state(
        self,
        user_id: int,
        conversation_stage: str = None,
        cta_variant: str = None,
        cta_shown: Optional[bool] = None,
    ) -> None:
        """Синхронизация состояния воронки в таблице leads для последнего лида пользователя."""
        updates = []
        values: List = []

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

        conn = self.get_connection()
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
        except Exception as e:
            logger.error(f"Error updating lead funnel state: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_lead_funnel_state_by_id(
        self,
        lead_id: int,
        conversation_stage: str = None,
        cta_variant: str = None,
        cta_shown: Optional[bool] = None,
    ) -> None:
        """Синхронизация состояния воронки для конкретного лида."""
        updates = []
        values: List = []

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

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            values.append(lead_id)
            cursor.execute(
                f"UPDATE leads SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values,
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating lead funnel state by id: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def track_event(
        self,
        user_id: int,
        event_type: str,
        payload: Optional[Dict] = None,
        lead_id: Optional[int] = None,
    ) -> int:
        """Запись события аналитики."""
        conn = self.get_connection()
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
        except Exception as e:
            logger.error(f"Error tracking analytics event: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

        try:
            from core_api_bridge import core_api_bridge

            core_lead_id = None
            if lead_id:
                lead = self.get_lead_by_id(lead_id) or {}
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

    # === CONVERSATIONS ===

    def add_message(self, user_id: int, role: str, message: str):
        """Добавление сообщения в историю диалога"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO conversations (user_id, role, message)
                VALUES (?, ?, ?)
            """, (user_id, role, message))

            conn.commit()
            logger.debug(f"Message added for user {user_id}, role {role}")

        except Exception as e:
            logger.error(f"Error adding message: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_conversation_history(self, user_id: int, limit: int = None) -> List[Dict]:
        """Получение истории диалога"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            limit = limit or config.MAX_HISTORY_MESSAGES

            cursor.execute("""
                SELECT role, message, timestamp
                FROM conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))

            rows = cursor.fetchall()
            # Возвращаем в обратном порядке (от старых к новым)
            return [dict(row) for row in reversed(rows)]

        finally:
            conn.close()

    def clear_conversation_history(self, user_id: int):
        """Очистка истории диалога"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
            conn.commit()
            logger.info(f"Conversation history cleared for user {user_id}")

        except Exception as e:
            logger.error(f"Error clearing conversation: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    # === LEADS ===

    def create_or_update_lead(self, user_id: int, lead_data: Dict) -> int:
        """Создание или обновление лида"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Проверяем уникальность по компании и email
            # Если изменилась компания или email = это НОВЫЙ лид!
            company = lead_data.get('company')
            email = lead_data.get('email')
            
            # Ищем существующий лид с ТЕМ ЖЕ company + email
            if company and email:
                cursor.execute(
                    "SELECT id FROM leads WHERE user_id = ? AND company = ? AND email = ?",
                    (user_id, company, email)
                )
            else:
                # Если нет компании или email, ищем по user_id
                cursor.execute("SELECT id FROM leads WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
            
            existing = cursor.fetchone()

            if existing:
                # Обновляем существующий лид
                lead_id = existing[0]

                # Фильтруем только допустимые колонки
                safe_data = {k: v for k, v in lead_data.items()
                             if v is not None and k in _LEADS_COLUMNS}

                if safe_data:
                    update_fields = [f"{key} = ?" for key in safe_data]
                    values = list(safe_data.values()) + [lead_id]
                    query = f"UPDATE leads SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                    cursor.execute(query, values)

                logger.info(f"Lead {lead_id} updated for user {user_id}")

            else:
                # Создаем новый лид — фильтруем допустимые колонки
                safe_data = {k: v for k, v in lead_data.items() if k in _LEADS_COLUMNS}
                fields = ['user_id'] + list(safe_data.keys())
                placeholders = ['?'] * len(fields)
                values = [user_id] + list(safe_data.values())

                query = f"INSERT INTO leads ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(query, values)

                lead_id = cursor.lastrowid
                logger.info(f"Lead {lead_id} created for user {user_id}")

            conn.commit()
            self._sync_lead_to_core(lead_id)
            return lead_id

        except Exception as e:
            logger.error(f"Error creating/updating lead: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_new_lead(self, user_id: int, lead_data: Dict) -> int:
        """Принудительное создание нового лида, без merge с предыдущим."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cleaned = {k: v for k, v in (lead_data or {}).items()
                       if v is not None and k in _LEADS_COLUMNS}
            fields = ["user_id"] + list(cleaned.keys())
            values = [user_id] + list(cleaned.values())
            placeholders = ["?"] * len(fields)

            query = f"INSERT INTO leads ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(query, values)
            lead_id = cursor.lastrowid
            conn.commit()
            logger.info(f"New lead {lead_id} created for user {user_id}")
            self._sync_lead_to_core(lead_id)
            return lead_id
        except Exception as e:
            logger.error(f"Error creating new lead: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_lead_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Получение последнего лида по user_id"""
        conn = self.get_connection()
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

            if row:
                user = self.get_user_by_id(user_id)
                telegram_user_id = (user or {}).get("telegram_id")
                return self._merge_lead_row_with_core(dict(row), telegram_user_id=telegram_user_id)
            return None

        finally:
            conn.close()

    def mark_lead_notification_sent(self, lead_id: int):
        """Помечаем что уведомление о лиде отправлено"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE leads
                SET notification_sent = 1
                WHERE id = ?
            """, (lead_id,))

            conn.commit()
            logger.info(f"Lead {lead_id} marked as notification sent")

        except Exception as e:
            logger.error(f"Error marking lead notification sent: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_lead_by_id(self, lead_id: int) -> Optional[Dict]:
        """Получение лида по lead_id"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()

            if row:
                local_lead = dict(row)
                user = self.get_user_by_id(local_lead["user_id"]) if local_lead.get("user_id") else None
                return self._merge_lead_row_with_core(local_lead, telegram_user_id=(user or {}).get("telegram_id"))
            return None

        finally:
            conn.close()

    def set_core_lead_id(self, lead_id: int, core_lead_id: str) -> None:
        """Сохраняет UUID лида из core-api для legacy лида."""
        conn = self.get_connection()
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
        except Exception as e:
            logger.error(f"Error setting core_lead_id for lead {lead_id}: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_all_leads(self, temperature: str = None, status: str = None,
                      limit: int = 100) -> List[Dict]:
        """Получение всех лидов с фильтрами"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            query = "SELECT * FROM leads WHERE 1=1"
            params = []

            if temperature:
                query += " AND temperature = ?"
                params.append(temperature)

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()
    
    def get_leads_ready_for_notification(self, idle_minutes: int = 5) -> List[Dict]:
        """
        Получение лидов готовых к уведомлению:
        - Прошло idle_minutes минут с последнего сообщения
        - Уведомление еще не отправлено
        - Лид теплый или горячий (или есть ключевые данные)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Ищем лидов где:
            # 1. last_message_at есть и прошло > idle_minutes минут
            # 2. notification_sent = 0
            # 3. Температура warm/hot ИЛИ есть контакты+боль
            idle_minutes = int(idle_minutes)  # ensure integer
            cursor.execute("""
                SELECT * FROM leads
                WHERE last_message_at IS NOT NULL
                AND notification_sent = 0
                AND (
                    datetime(last_message_at, '+' || ? || ' minutes') <= datetime('now')
                )
                AND (
                    temperature IN ('warm', 'hot')
                    OR (
                        name IS NOT NULL
                        AND (email IS NOT NULL OR phone IS NOT NULL)
                        AND pain_point IS NOT NULL
                    )
                )
                ORDER BY last_message_at DESC
            """, (str(idle_minutes),))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        finally:
            conn.close()
    
    def update_lead_last_message_time(self, user_id: int):
        """Обновление времени последнего сообщения лида"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE leads
                SET last_message_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))
            
            conn.commit()
            logger.debug(f"Updated last_message_at for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error updating last_message_at: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # === KNOWLEDGE BASE / RAG ===
    
    def get_successful_conversations(self, limit: int = 50) -> List[Dict]:
        """
        Получение успешных диалогов (warm/hot лиды) для RAG
        
        Returns:
            Список словарей с полными диалогами и метаданными лидов
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Получаем успешные лиды
            cursor.execute("""
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
                LIMIT ?
            """, (limit,))
            
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

            messages_by_user = {}
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
                user_id = lead['user_id']
                result.append({
                    'lead_id': lead['id'],
                    'user_id': user_id,
                    'service_category': lead.get('service_category'),
                    'specific_need': lead.get('specific_need'),
                    'pain_point': lead.get('pain_point'),
                    'industry': lead.get('industry'),
                    'temperature': lead.get('temperature'),
                    'messages': messages_by_user.get(user_id, []),
                })
            
            logger.info(f"Retrieved {len(result)} successful conversations for RAG")
            return result
            
        finally:
            conn.close()
    
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
        conn = self.get_connection()
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
            
            params = [service_category]
            
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

            messages_by_user = {}
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
                result.append({
                    'lead_id': lead['id'],
                    'service_category': lead.get('service_category'),
                    'specific_need': lead.get('specific_need'),
                    'pain_point': lead.get('pain_point'),
                    'temperature': lead.get('temperature'),
                    'messages': messages_by_user.get(lead['user_id'], []),
                })
            
            return result
            
        finally:
            conn.close()

    # === ADMIN NOTIFICATIONS ===

    def create_notification(self, lead_id: int, notification_type: str,
                            message: str) -> int:
        """Создание уведомления для админа"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO admin_notifications (lead_id, notification_type, message)
                VALUES (?, ?, ?)
            """, (lead_id, notification_type, message))

            conn.commit()
            notification_id = cursor.lastrowid

            logger.info(f"Notification {notification_id} created for lead {lead_id}")
            return notification_id

        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    # === STATISTICS ===

    def get_statistics(self, days: int = 30) -> Dict:
        """Получение статистики"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            stats = {}

            # Общее количество пользователей
            cursor.execute("SELECT COUNT(*) FROM users")
            stats['total_users'] = cursor.fetchone()[0]

            # Новые пользователи за период
            cursor.execute("""
                SELECT COUNT(*) FROM users
                WHERE created_at >= datetime('now', '-' || ? || ' days')
            """, (days,))
            stats['new_users'] = cursor.fetchone()[0]

            # Общее количество лидов
            cursor.execute("SELECT COUNT(*) FROM leads")
            stats['total_leads'] = cursor.fetchone()[0]

            # Лиды по температуре
            for temp in ['hot', 'warm', 'cold']:
                cursor.execute("SELECT COUNT(*) FROM leads WHERE temperature = ?", (temp,))
                stats[f'{temp}_leads'] = cursor.fetchone()[0]

            # Общее количество сообщений
            cursor.execute("SELECT COUNT(*) FROM conversations")
            stats['total_messages'] = cursor.fetchone()[0]

            # Средняя длина диалога
            cursor.execute("""
                SELECT AVG(msg_count)
                FROM (
                    SELECT user_id, COUNT(*) as msg_count
                    FROM conversations
                    GROUP BY user_id
                )
            """)
            result = cursor.fetchone()[0]
            stats['avg_conversation_length'] = round(result, 1) if result else 0

            # Lead Magnets
            cursor.execute("SELECT COUNT(*) FROM leads WHERE lead_magnet_type = 'consultation'")
            stats['consultations'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE lead_magnet_type = 'checklist'")
            stats['checklists'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE lead_magnet_type IN ('demo', 'demo_analysis')")
            stats['demos'] = cursor.fetchone()[0]

            # Funnel stages (users)
            for stage in ['discover', 'diagnose', 'qualify', 'propose', 'handoff']:
                cursor.execute("SELECT COUNT(*) FROM users WHERE conversation_stage = ?", (stage,))
                stats[f'stage_{stage}'] = cursor.fetchone()[0]

            # CTA воронки
            cursor.execute("SELECT COUNT(*) FROM users WHERE cta_shown = 1")
            stats['cta_shown_users'] = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM analytics_events
                WHERE event_type = 'cta_clicked'
            """)
            stats['cta_clicks'] = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM analytics_events
                WHERE event_type = 'handoff_done'
            """)
            stats['handoff_done'] = cursor.fetchone()[0]

            return stats

        finally:
            conn.close()

    def get_funnel_report(self, days: int = 30) -> Dict:
        """
        SQL-отчет по этапам воронки за период.
        Основан на событиях analytics_events и активности в conversations.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            report: Dict[str, Dict] = {}
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

    def get_ab_cta_report(self, days: int = 30) -> Dict:
        """
        SQL-отчет по A/B вариантам CTA за период.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            window = str(days)
            variants = {}

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
