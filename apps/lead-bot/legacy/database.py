"""
Работа с SQLite базой данных
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from config import Config
config = Config()

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с SQLite базой данных"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
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

            conn.commit()
            # Миграция: добавляем таблицу для состояний чатов
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
            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    # === USERS ===

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
            # Миграция: добавляем таблицу для состояний чатов
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
            # Миграция: добавляем таблицу для состояний чатов
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
            # Миграция: добавляем таблицу для состояний чатов
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
            # Миграция: добавляем таблицу для состояний чатов
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
            # Миграция: добавляем таблицу для состояний чатов
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
            # Миграция: добавляем таблицу для состояний чатов
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
            # Миграция: добавляем таблицу для состояний чатов
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

            cursor.execute("SELECT COUNT(*) FROM leads WHERE lead_magnet_type = 'demo_analysis'")
            stats['demos'] = cursor.fetchone()[0]

            return stats

        finally:
            conn.close()


# Создание глобального экземпляра базы данных
db = Database()


if __name__ == '__main__':
    # Инициализация логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Initializing database...")
    db = Database()
    print("Database initialized successfully!")

    # === CHAT STATES ===

    def is_chat_enabled(self, chat_id: int) -> bool:
        """Проверка, включен ли чат"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT is_enabled FROM chat_states WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()
            
            # Если записи нет, считаем чат включенным (по умолчанию)
            return row[0] if row else True
            
        finally:
            conn.close()

    def set_chat_enabled(self, chat_id: int, enabled: bool):
        """Включение/отключение чата"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO chat_states (chat_id, is_enabled, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    is_enabled = excluded.is_enabled,
                    updated_at = CURRENT_TIMESTAMP
            """, (chat_id, enabled))
            
            conn.commit()
            # Миграция: добавляем таблицу для состояний чатов
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
            logger.info(f"Chat {chat_id} {'enabled' if enabled else 'disabled'}")
            
        except Exception as e:
            logger.error(f"Error setting chat enabled state: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_disabled_chats(self) -> list:
        """Получение списка отключенных чатов"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT chat_id FROM chat_states WHERE is_enabled = 0")
            return [row[0] for row in cursor.fetchall()]
            
        finally:
            conn.close()

    # === CHAT STATES ===

    def is_chat_enabled(self, chat_id: int) -> bool:
        """Проверка, включен ли чат"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT is_enabled FROM chat_states WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()
            
            # Если записи нет, считаем чат включенным (по умолчанию)
            return row[0] if row else True
            
        finally:
            conn.close()

    def set_chat_enabled(self, chat_id: int, enabled: bool):
        """Включение/отключение чата"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO chat_states (chat_id, is_enabled, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    is_enabled = excluded.is_enabled,
                    updated_at = CURRENT_TIMESTAMP
            """, (chat_id, enabled))
            
            conn.commit()
            logger.info(f"Chat {chat_id} {'enabled' if enabled else 'disabled'}")
            
        except Exception as e:
            logger.error(f"Error setting chat enabled state: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_disabled_chats(self) -> list:
        """Получение списка отключенных чатов"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT chat_id FROM chat_states WHERE is_enabled = 0")
            return [row[0] for row in cursor.fetchall()]
            
        finally:
            conn.close()

    # === CHAT STATES ===

    def is_chat_enabled(self, chat_id: int) -> bool:
        """Проверка, включен ли чат"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT is_enabled FROM chat_states WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()
            
            # Если записи нет, считаем чат включенным (по умолчанию)
            return row[0] if row else True
            
        finally:
            conn.close()

    def set_chat_enabled(self, chat_id: int, enabled: bool):
        """Включение/отключение чата"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO chat_states (chat_id, is_enabled, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    is_enabled = excluded.is_enabled,
                    updated_at = CURRENT_TIMESTAMP
            """, (chat_id, enabled))
            
            conn.commit()
            logger.info(f"Chat {chat_id} {'enabled' if enabled else 'disabled'}")
            
        except Exception as e:
            logger.error(f"Error setting chat enabled state: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_disabled_chats(self) -> list:
        """Получение списка отключенных чатов"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT chat_id FROM chat_states WHERE is_enabled = 0")
            return [row[0] for row in cursor.fetchall()]
            
        finally:
            conn.close()
