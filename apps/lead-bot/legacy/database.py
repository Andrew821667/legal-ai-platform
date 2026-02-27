"""
Работа с SQLite базой данных
"""
import sqlite3
import logging
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from config import Config
config = Config()

logger = logging.getLogger(__name__)


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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_states_chat_id ON chat_states(chat_id)")
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
                return dict(row)
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
                return dict(row)
            return None

        finally:
            conn.close()

    def get_recent_users(self, limit: int = 20) -> List[Dict]:
        """Получение последних активных пользователей."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT *
                FROM users
                ORDER BY COALESCE(last_interaction, created_at) DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
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
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    consent_given,
                    consent_date,
                    consent_revoked,
                    consent_revoked_at,
                    transborder_consent,
                    transborder_consent_date,
                    marketing_consent,
                    marketing_consent_date
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {}
            return dict(row)
        finally:
            conn.close()

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

            conn.commit()
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

    def export_user_data(self, user_id: int) -> Dict:
        """Экспорт данных пользователя и связанной анкеты."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                return {}

            cursor.execute(
                "SELECT * FROM leads WHERE user_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 1",
                (user_id,),
            )
            lead = cursor.fetchone()

            return {
                "user": dict(user),
                "lead": dict(lead) if lead else {},
                "consent": {
                    "consent_given": bool(user["consent_given"]),
                    "consent_date": user["consent_date"],
                    "consent_revoked": bool(user["consent_revoked"]),
                    "consent_revoked_at": user["consent_revoked_at"],
                    "transborder_consent": bool(user["transborder_consent"]),
                    "transborder_consent_date": user["transborder_consent_date"],
                    "marketing_consent": bool(user["marketing_consent"]),
                    "marketing_consent_date": user["marketing_consent_date"],
                },
            }
        finally:
            conn.close()

    def update_user_fields(self, user_id: int, fields: Dict[str, str]) -> bool:
        """Обновление полей профиля пользователя."""
        if not fields:
            return False
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
        """Синхронизация состояния воронки в таблице leads для аналитики."""
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
                f"UPDATE leads SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                values,
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating lead funnel state: {e}")
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
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error tracking analytics event: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

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

                update_fields = []
                values = []

                for key, value in lead_data.items():
                    if value is not None:
                        update_fields.append(f"{key} = ?")
                        values.append(value)

                if update_fields:
                    values.append(lead_id)
                    query = f"UPDATE leads SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                    cursor.execute(query, values)

                logger.info(f"Lead {lead_id} updated for user {user_id}")

            else:
                # Создаем новый лид
                fields = ['user_id'] + list(lead_data.keys())
                placeholders = ['?'] * len(fields)
                values = [user_id] + list(lead_data.values())

                query = f"INSERT INTO leads ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(query, values)

                lead_id = cursor.lastrowid
                logger.info(f"Lead {lead_id} created for user {user_id}")

            conn.commit()
            return lead_id

        except Exception as e:
            logger.error(f"Error creating/updating lead: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_lead_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Получение лида по user_id"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM leads WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
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
                return dict(row)
            return None

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
            cursor.execute(f"""
                SELECT * FROM leads
                WHERE last_message_at IS NOT NULL
                AND notification_sent = 0
                AND (
                    datetime(last_message_at, '+{idle_minutes} minutes') <= datetime('now')
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
            """)
            
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
            
            # Для каждого лида получаем историю диалога
            result = []
            for lead in leads:
                user_id = lead['user_id']
                
                # Получаем сообщения диалога
                cursor.execute("""
                    SELECT role, message, timestamp
                    FROM conversations
                    WHERE user_id = ?
                    ORDER BY timestamp ASC
                """, (user_id,))
                
                messages = [dict(row) for row in cursor.fetchall()]
                
                # Формируем полный объект
                result.append({
                    'lead_id': lead['id'],
                    'user_id': user_id,
                    'service_category': lead.get('service_category'),
                    'specific_need': lead.get('specific_need'),
                    'pain_point': lead.get('pain_point'),
                    'industry': lead.get('industry'),
                    'temperature': lead.get('temperature'),
                    'messages': messages
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
            
            # Добавляем сообщения для каждого лида
            result = []
            for lead in leads:
                cursor.execute("""
                    SELECT role, message, timestamp
                    FROM conversations
                    WHERE user_id = ?
                    ORDER BY timestamp ASC
                """, (lead['user_id'],))
                
                messages = [dict(row) for row in cursor.fetchall()]
                
                result.append({
                    'lead_id': lead['id'],
                    'service_category': lead.get('service_category'),
                    'specific_need': lead.get('specific_need'),
                    'pain_point': lead.get('pain_point'),
                    'temperature': lead.get('temperature'),
                    'messages': messages
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
