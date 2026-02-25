import logging
import database
from config import Config
config = Config()

logger = logging.getLogger(__name__)

class AdminInterface:
    def __init__(self, db):
        self.db = db

    def format_leads_list(self, temperature=None, status=None, limit=20):
        try:
            leads = self.db.get_all_leads(temperature, status, limit)
            if not leads:
                return "📋 СПИСОК ЛИДОВ\n\nЛидов не найдено"
            
            message = f"📋 СПИСОК ЛИДОВ ({len(leads)})\n\n"
            for i, lead in enumerate(leads, 1):
                # lead - это dict, получаем значения безопасно
                name = lead.get('name', 'N/A') or lead.get('full_name', 'N/A')
                company = lead.get('company', '')
                temp = lead.get('temperature', 'unknown')
                emoji = {'hot': '🔥', 'warm': '♨️', 'cold': '❄️'}.get(temp, '❓')
                message += f"{i}. {emoji} {name} ({company})\n"
            return message
        except Exception as e:
            logger.error(f"Error in format_leads_list: {e}", exc_info=True)
            return f"❌ Ошибка: {e}"
    
    def format_statistics(self, days=30):
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Пользователи
            cursor.execute('SELECT COUNT(*) FROM users')
            users = cursor.fetchone()[0]
            
            # Сообщения
            cursor.execute('SELECT COUNT(*) FROM conversations')
            messages = cursor.fetchone()[0]
            
            # Лиды
            cursor.execute('SELECT COUNT(*) FROM leads')
            total_leads = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM leads WHERE temperature="hot"')
            hot = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM leads WHERE temperature="warm"')
            warm = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM leads WHERE temperature="cold"')
            cold = cursor.fetchone()[0]
            
            message = (
                f"📊 СТАТИСТИКА\n\n"
                f"👥 Пользователей: {users}\n"
                f"💬 Сообщений: {messages}\n"
                f"📋 Лидов: {total_leads}\n"
                f"  🔥 Горячих: {hot}\n"
                f"  ♨️ Теплых: {warm}\n"
                f"  ❄️ Холодных: {cold}"
            )
            return message
        except Exception as e:
            logger.error(f"Error: {e}")
            return f"❌ Ошибка: {e}"
    
    def export_leads_to_csv(self):
        return "📥 Экспорт лидов"
    
    def get_conversation_history_text(self, telegram_id):
        return "📝 История диалога"
    
    def send_admin_notification(self, *args, **kwargs):
        pass

# Инициализируем глобальный объект
try:
    from database import Database
    _db = Database()
    admin_interface = AdminInterface(_db)
except Exception as e:
    print(f"Warning: Could not initialize admin_interface: {e}")
    admin_interface = None
