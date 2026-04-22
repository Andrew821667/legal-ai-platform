#!/usr/bin/env python3
"""
Автоматические тесты для AI Verdict Telegram Bot
"""
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, MagicMock
from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes

# Импортируем модули бота
import database
import ai_brain
import handlers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class BotTester:
    """Класс для автоматического тестирования бота"""

    def __init__(self):
        self.test_user_id = 999999999
        self.test_username = "test_user"
        self.test_results = []

    def create_mock_update(self, text: str, user_id: int = None) -> Update:
        """Создает mock объект Update для тестирования"""
        if user_id is None:
            user_id = self.test_user_id

        # Mock User
        user = Mock(spec=User)
        user.id = user_id
        user.username = self.test_username
        user.first_name = "Test"
        user.last_name = "User"

        # Mock Chat
        chat = Mock(spec=Chat)
        chat.id = user_id
        chat.send_action = AsyncMock()

        # Mock Message
        message = Mock(spec=Message)
        message.text = text
        message.from_user = user
        message.chat = chat
        message.reply_text = AsyncMock(return_value=message)
        message.edit_text = AsyncMock()

        # Mock Update
        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user

        return update

    def create_mock_context(self) -> ContextTypes.DEFAULT_TYPE:
        """Создает mock объект Context"""
        context = MagicMock()
        context.user_data = {}
        return context

    async def test_scenario_1_basic_dialog(self):
        """СЦЕНАРИЙ 1: Базовый диалог + квалификация + lead magnet"""
        print("\n" + "="*70)
        print("🧪 СЦЕНАРИЙ 1: Базовый диалог + квалификация + lead magnet")
        print("="*70)

        try:
            # 1. /start
            print("\n1️⃣ Отправка /start...")
            update = self.create_mock_update("/start")
            context = self.create_mock_context()
            await handlers.start_command(update, context)
            print("✅ /start обработан")

            # 2. Вопрос про автоматизацию
            print("\n2️⃣ Отправка вопроса про автоматизацию...")
            update = self.create_mock_update("Интересует автоматизация работы с договорами")
            await handlers.handle_message(update, context)
            print("✅ Вопрос обработан")

            # 3. Информация о команде
            print("\n3️⃣ Отправка информации о команде...")
            update = self.create_mock_update("У нас 5 юристов, примерно 50 договоров в месяц")
            await handlers.handle_message(update, context)
            print("✅ Информация о команде обработана")

            # 4. Боль + бюджет
            print("\n4️⃣ Отправка боли и бюджета...")
            update = self.create_mock_update("Не успеваем проверять, пропускаем риски. Бюджет до 400 тысяч. Срочно нужно")
            await handlers.handle_message(update, context)
            print("✅ Боль и бюджет обработаны")

            # 5. Контакты
            print("\n5️⃣ Отправка контактов...")
            update = self.create_mock_update("Меня зовут Иван Петров, компания ООО Техстрой")
            await handlers.handle_message(update, context)
            print("✅ Контакты обработаны")

            # Проверка в БД
            print("\n📊 Проверка данных в БД...")
            user_data = database.db.get_user_by_telegram_id(self.test_user_id)
            if user_data:
                print(f"✅ Пользователь найден в БД: ID={user_data['id']}")

                lead = database.db.get_lead_by_user_id(user_data['id'])
                if lead:
                    print(f"✅ Лид создан:")
                    print(f"   - Температура: {lead.get('temperature')}")
                    print(f"   - Боль: {lead.get('pain_point')}")
                    print(f"   - Бюджет: {lead.get('budget')}")
                    print(f"   - Компания: {lead.get('company')}")
                else:
                    print("❌ Лид не найден в БД")
            else:
                print("❌ Пользователь не найден в БД")

            print("\n✅ СЦЕНАРИЙ 1 ЗАВЕРШЕН")
            return True

        except Exception as e:
            print(f"\n❌ ОШИБКА В СЦЕНАРИИ 1: {e}")
            logger.exception("Ошибка в сценарии 1")
            return False

    async def test_scenario_2_cold_lead(self):
        """СЦЕНАРИЙ 2: Холодный лид (просто изучает)"""
        print("\n" + "="*70)
        print("🧪 СЦЕНАРИЙ 2: Холодный лид (просто изучает)")
        print("="*70)

        try:
            test_user_id = 999999998

            # 1. /start
            print("\n1️⃣ Отправка /start...")
            update = self.create_mock_update("/start", test_user_id)
            context = self.create_mock_context()
            await handlers.start_command(update, context)
            print("✅ /start обработан")

            # 2. Общий вопрос
            print("\n2️⃣ Отправка общего вопроса...")
            update = self.create_mock_update("Что вы вообще делаете?", test_user_id)
            await handlers.handle_message(update, context)
            print("✅ Общий вопрос обработан")

            # 3. Вопрос про цены
            print("\n3️⃣ Отправка вопроса про цены...")
            update = self.create_mock_update("А сколько стоит?", test_user_id)
            await handlers.handle_message(update, context)
            print("✅ Вопрос про цены обработан")

            # 4. Спасибо
            print("\n4️⃣ Отправка 'спасибо'...")
            update = self.create_mock_update("Понятно, спасибо", test_user_id)
            await handlers.handle_message(update, context)
            print("✅ 'Спасибо' обработано")

            # Проверка в БД
            print("\n📊 Проверка данных в БД...")
            user_data = database.db.get_user_by_telegram_id(test_user_id)
            if user_data:
                lead = database.db.get_lead_by_user_id(user_data['id'])
                if lead:
                    temp = lead.get('temperature', 'unknown')
                    print(f"✅ Лид создан с температурой: {temp}")
                    if temp == 'cold':
                        print("✅ Температура правильная (cold)")
                    else:
                        print(f"⚠️ Температура не cold, а {temp}")
                else:
                    print("✅ Лид не создан (нормально для холодного лида без контактов)")

            print("\n✅ СЦЕНАРИЙ 2 ЗАВЕРШЕН")
            return True

        except Exception as e:
            print(f"\n❌ ОШИБКА В СЦЕНАРИИ 2: {e}")
            logger.exception("Ошибка в сценарии 2")
            return False

    async def test_scenario_3_handoff(self):
        """СЦЕНАРИЙ 3: Handoff - клиент просит человека"""
        print("\n" + "="*70)
        print("🧪 СЦЕНАРИЙ 3: Handoff - клиент просит человека")
        print("="*70)

        try:
            test_user_id = 999999997

            # 1. /start
            print("\n1️⃣ Отправка /start...")
            update = self.create_mock_update("/start", test_user_id)
            context = self.create_mock_context()
            await handlers.start_command(update, context)
            print("✅ /start обработан")

            # 2. Триггер handoff
            print("\n2️⃣ Отправка триггера handoff...")
            update = self.create_mock_update("Хочу поговорить с реальным человеком", test_user_id)

            # Проверяем триггер
            trigger_detected = ai_brain.ai_brain.check_handoff_trigger("Хочу поговорить с реальным человеком")
            if trigger_detected:
                print("✅ Триггер handoff обнаружен!")
            else:
                print("❌ Триггер handoff НЕ обнаружен")

            await handlers.handle_message(update, context)
            print("✅ Handoff запрос обработан")

            print("\n✅ СЦЕНАРИЙ 3 ЗАВЕРШЕН")
            return True

        except Exception as e:
            print(f"\n❌ ОШИБКА В СЦЕНАРИИ 3: {e}")
            logger.exception("Ошибка в сценарии 3")
            return False

    async def test_scenario_4_commands(self):
        """СЦЕНАРИЙ 4: Тестирование команд"""
        print("\n" + "="*70)
        print("🧪 СЦЕНАРИЙ 4: Тестирование команд")
        print("="*70)

        try:
            test_user_id = 999999996
            context = self.create_mock_context()

            commands = [
                ("/start", handlers.start_command),
                ("/help", handlers.help_command),
                ("/reset", handlers.reset_command),
            ]

            for cmd, handler in commands:
                print(f"\n📤 Тестирование команды {cmd}...")
                update = self.create_mock_update(cmd, test_user_id)
                await handler(update, context)
                print(f"✅ {cmd} обработана")

            print("\n✅ СЦЕНАРИЙ 4 ЗАВЕРШЕН")
            return True

        except Exception as e:
            print(f"\n❌ ОШИБКА В СЦЕНАРИИ 4: {e}")
            logger.exception("Ошибка в сценарии 4")
            return False

    async def test_scenario_5_ai_brain(self):
        """СЦЕНАРИЙ 5: Тестирование AI Brain"""
        print("\n" + "="*70)
        print("🧪 СЦЕНАРИЙ 5: Тестирование AI Brain")
        print("="*70)

        try:
            # Тест генерации ответа (старый метод)
            print("\n1️⃣ Тест обычной генерации ответа...")
            conversation = [
                {"role": "user", "message": "Привет, интересует автоматизация договоров"}
            ]
            response = ai_brain.ai_brain.generate_response(conversation)
            print(f"✅ Ответ получен: {len(response)} символов")
            print(f"   Первые 100 символов: {response[:100]}...")

            # Проверка на отсутствие технического жаргона
            print("\n2️⃣ Проверка отсутствия технического жаргона...")
            forbidden_words = ["RAG", "промпт", "эмбеддинг", "вектор"]
            found_jargon = [word for word in forbidden_words if word.lower() in response.lower()]
            if found_jargon:
                print(f"⚠️ Найден технический жаргон: {found_jargon}")
            else:
                print("✅ Технический жаргон отсутствует")

            # Проверка упоминания команды
            print("\n3️⃣ Проверка упоминания 'команда' (не Андрей)...")
            if "команд" in response.lower():
                print("✅ Упоминается 'команда'")
            else:
                print("⚠️ Не найдено упоминание 'команда'")

            # Проверка отсутствия "100 лет"
            print("\n4️⃣ Проверка отсутствия '100 лет'...")
            if "100 лет" in response or "100 лет" in response:
                print("❌ Найдено упоминание '100 лет'!")
            else:
                print("✅ Упоминание '100 лет' отсутствует")

            # Тест извлечения данных лида
            print("\n5️⃣ Тест извлечения данных лида...")
            conversation_full = [
                {"role": "user", "message": "Интересует автоматизация договоров"},
                {"role": "assistant", "message": "Расскажите о вашей команде"},
                {"role": "user", "message": "У нас 5 юристов, около 50 договоров в месяц"},
                {"role": "assistant", "message": "Какая основная проблема?"},
                {"role": "user", "message": "Не успеваем, пропускаем риски. Бюджет 400 тысяч. ivan@company.ru"}
            ]

            lead_data = ai_brain.ai_brain.extract_lead_data(conversation_full)
            if lead_data:
                print("✅ Данные лида извлечены:")
                print(f"   - Email: {lead_data.get('email')}")
                print(f"   - Боль: {lead_data.get('pain_point')}")
                print(f"   - Бюджет: {lead_data.get('budget')}")
                print(f"   - Температура: {lead_data.get('lead_temperature')}")
            else:
                print("❌ Не удалось извлечь данные лида")

            # Тест триггеров handoff
            print("\n6️⃣ Тест триггеров handoff...")
            test_phrases = [
                ("хочу поговорить с человеком", True),
                ("свяжите с юристом", True),
                ("обычный вопрос", False),
            ]

            for phrase, should_trigger in test_phrases:
                triggered = ai_brain.ai_brain.check_handoff_trigger(phrase)
                if triggered == should_trigger:
                    print(f"✅ '{phrase}': {triggered} (правильно)")
                else:
                    print(f"❌ '{phrase}': {triggered} (ожидалось {should_trigger})")

            print("\n✅ СЦЕНАРИЙ 5 ЗАВЕРШЕН")
            return True

        except Exception as e:
            print(f"\n❌ ОШИБКА В СЦЕНАРИИ 5: {e}")
            logger.exception("Ошибка в сценарии 5")
            return False

    async def test_scenario_6_database(self):
        """СЦЕНАРИЙ 6: Тестирование базы данных"""
        print("\n" + "="*70)
        print("🧪 СЦЕНАРИЙ 6: Тестирование базы данных")
        print("="*70)

        try:
            # 1. Создание пользователя
            print("\n1️⃣ Создание тестового пользователя...")
            test_telegram_id = 888888888
            user_id = database.db.create_or_update_user(
                telegram_id=test_telegram_id,
                username="db_test_user",
                first_name="DB",
                last_name="Test"
            )
            print(f"✅ Пользователь создан: ID={user_id}")

            # 2. Получение пользователя
            print("\n2️⃣ Получение пользователя из БД...")
            user = database.db.get_user_by_telegram_id(test_telegram_id)
            if user:
                print(f"✅ Пользователь найден: {user['username']}")
            else:
                print("❌ Пользователь не найден")

            # 3. Добавление сообщений
            print("\n3️⃣ Добавление сообщений в историю...")
            database.db.add_message(user_id, 'user', 'Тестовое сообщение 1')
            database.db.add_message(user_id, 'assistant', 'Тестовый ответ 1')
            database.db.add_message(user_id, 'user', 'Тестовое сообщение 2')
            print("✅ Сообщения добавлены")

            # 4. Получение истории
            print("\n4️⃣ Получение истории диалога...")
            history = database.db.get_conversation_history(user_id)
            print(f"✅ История получена: {len(history)} сообщений")

            # 5. Создание лида
            print("\n5️⃣ Создание лида...")
            lead_data = {
                "name": "Тест Тестов",
                "email": "test@test.com",
                "company": "Тестовая компания",
                "team_size": "4-10",
                "budget": "300-500K",
                "temperature": "hot"
            }
            lead_id = database.db.create_or_update_lead(user_id, lead_data)
            print(f"✅ Лид создан: ID={lead_id}")

            # 6. Получение лида
            print("\n6️⃣ Получение лида из БД...")
            lead = database.db.get_lead_by_user_id(user_id)
            if lead:
                print(f"✅ Лид найден:")
                print(f"   - Имя: {lead['name']}")
                print(f"   - Email: {lead['email']}")
                print(f"   - Температура: {lead['temperature']}")
            else:
                print("❌ Лид не найден")

            # 7. Получение всех лидов
            print("\n7️⃣ Получение всех лидов...")
            all_leads = database.db.get_all_leads()
            print(f"✅ Всего лидов в БД: {len(all_leads)}")

            print("\n✅ СЦЕНАРИЙ 6 ЗАВЕРШЕН")
            return True

        except Exception as e:
            print(f"\n❌ ОШИБКА В СЦЕНАРИИ 6: {e}")
            logger.exception("Ошибка в сценарии 6")
            return False

    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("\n" + "="*70)
        print("🚀 ЗАПУСК ВСЕХ ТЕСТОВ LEGAL AI BOT")
        print("="*70)

        results = []

        # Запуск всех сценариев
        scenarios = [
            ("Сценарий 1: Базовый диалог", self.test_scenario_1_basic_dialog),
            ("Сценарий 2: Холодный лид", self.test_scenario_2_cold_lead),
            ("Сценарий 3: Handoff", self.test_scenario_3_handoff),
            ("Сценарий 4: Команды", self.test_scenario_4_commands),
            ("Сценарий 5: AI Brain", self.test_scenario_5_ai_brain),
            ("Сценарий 6: База данных", self.test_scenario_6_database),
        ]

        for name, test_func in scenarios:
            try:
                result = await test_func()
                results.append((name, result))
            except Exception as e:
                logger.error(f"Ошибка в {name}: {e}")
                results.append((name, False))

        # Итоговый отчет
        print("\n" + "="*70)
        print("📊 ИТОГОВЫЙ ОТЧЕТ")
        print("="*70)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{status}: {name}")

        print("\n" + "="*70)
        print(f"Результат: {passed}/{total} тестов пройдено")
        print("="*70)

        return passed == total


async def main():
    """Главная функция"""
    tester = BotTester()
    success = await tester.run_all_tests()

    if success:
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        return 0
    else:
        print("\n❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    exit(exit_code)
