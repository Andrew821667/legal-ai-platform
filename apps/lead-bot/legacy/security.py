"""
Модуль безопасности и защиты от атак
"""
import time
import logging
from typing import Dict, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta
import database

logger = logging.getLogger(__name__)


class SecurityManager:
    """Управление безопасностью и защита от атак"""

    def __init__(self):
        # Rate limiting: хранение временных меток сообщений для каждого пользователя
        self.message_timestamps = defaultdict(deque)

        # Токен-трекинг: сколько токенов потратил каждый пользователь
        self.token_usage = defaultdict(int)

        # Blacklist: заблокированные пользователи
        self.blacklist = set()

        # Временные блокировки (cooldown)
        self.cooldowns = {}

        # Подозрительная активность
        self.suspicious_users = defaultdict(int)

        # Время начала сбора статистики
        self.stats_start_time = datetime.now()

        # Настройки лимитов
        self.RATE_LIMITS = {
            'messages_per_minute': 10,    # Макс 10 сообщений в минуту
            'messages_per_hour': 50,      # Макс 50 сообщений в час
            'messages_per_day': 200,      # Макс 200 сообщений в день
        }

        self.TOKEN_LIMITS = {
            'per_day': 50000,             # Макс 50К токенов в день на пользователя
            'per_week': 200000,           # Макс 200К токенов в неделю
        }

        self.COOLDOWN_SECONDS = 1  # Минимум 1 секунда между сообщениями (было 2)
        self.MAX_MESSAGE_LENGTH = 4000  # Макс длина сообщения (увеличено с 2000 до 4000)

        self.TOTAL_DAILY_BUDGET = 100000  # Общий дневной бюджет токенов для всех
        self.total_tokens_today = 0
        self.budget_reset_time = datetime.now() + timedelta(days=1)

        logger.info("Security Manager initialized")

    def check_rate_limit(self, user_id: int) -> tuple[bool, Optional[str]]:
        """
        Проверка rate limiting

        Returns:
            (allowed, reason) - True если разрешено, False + причина если заблокировано
        """
        now = time.time()
        user_messages = self.message_timestamps[user_id]

        # Удаляем старые временные метки (старше 1 дня)
        day_ago = now - 86400
        while user_messages and user_messages[0] < day_ago:
            user_messages.popleft()

        # Проверяем лимиты
        minute_ago = now - 60
        hour_ago = now - 3600

        messages_last_minute = sum(1 for ts in user_messages if ts > minute_ago)
        messages_last_hour = sum(1 for ts in user_messages if ts > hour_ago)
        messages_last_day = len(user_messages)

        if messages_last_minute >= self.RATE_LIMITS['messages_per_minute']:
            logger.warning(f"Rate limit exceeded for user {user_id}: {messages_last_minute} msgs/min")
            return False, f"Слишком много сообщений! Пожалуйста, подождите минуту. (Лимит: {self.RATE_LIMITS['messages_per_minute']} сообщений в минуту)"

        if messages_last_hour >= self.RATE_LIMITS['messages_per_hour']:
            logger.warning(f"Rate limit exceeded for user {user_id}: {messages_last_hour} msgs/hour")
            return False, f"Превышен лимит сообщений в час. Пожалуйста, подождите. (Лимит: {self.RATE_LIMITS['messages_per_hour']} сообщений в час)"

        if messages_last_day >= self.RATE_LIMITS['messages_per_day']:
            logger.warning(f"Rate limit exceeded for user {user_id}: {messages_last_day} msgs/day")
            return False, f"Превышен дневной лимит сообщений. Попробуйте завтра. (Лимит: {self.RATE_LIMITS['messages_per_day']} сообщений в день)"

        # Все проверки пройдены
        user_messages.append(now)
        return True, None

    def check_cooldown(self, user_id: int) -> tuple[bool, Optional[str]]:
        """
        Проверка cooldown между сообщениями

        Returns:
            (allowed, reason)
        """
        now = time.time()

        if user_id in self.cooldowns:
            last_message_time = self.cooldowns[user_id]
            time_since_last = now - last_message_time

            if time_since_last < self.COOLDOWN_SECONDS:
                wait_time = self.COOLDOWN_SECONDS - time_since_last
                return False, f"Подождите {wait_time:.1f} секунд перед следующим сообщением."

        self.cooldowns[user_id] = now
        return True, None

    def check_message_length(self, message: str) -> tuple[bool, Optional[str]]:
        """Проверка длины сообщения"""
        if len(message) > self.MAX_MESSAGE_LENGTH:
            return False, f"Сообщение слишком длинное! Максимум {self.MAX_MESSAGE_LENGTH} символов. (У вас: {len(message)})"
        return True, None

    def check_token_limit(self, user_id: int) -> tuple[bool, Optional[str]]:
        """Проверка лимита токенов для пользователя"""
        # TODO: Реализовать отслеживание токенов из БД
        # Пока возвращаем True
        return True, None

    def check_total_budget(self, estimated_tokens: int = 1000) -> tuple[bool, Optional[str]]:
        """Проверка общего дневного бюджета"""
        now = datetime.now()

        # Сброс счетчика в полночь
        if now > self.budget_reset_time:
            self.total_tokens_today = 0
            self.budget_reset_time = now + timedelta(days=1)
            logger.info("Daily token budget reset")

        if self.total_tokens_today + estimated_tokens > self.TOTAL_DAILY_BUDGET:
            logger.error(f"Daily budget exceeded! Used: {self.total_tokens_today}, Budget: {self.TOTAL_DAILY_BUDGET}")
            return False, "Извините, дневной лимит запросов исчерпан. Попробуйте завтра или свяжитесь с нашей командой напрямую."

        return True, None

    def estimate_tokens(self, text: str) -> int:
        """
        Оценка количества токенов в тексте

        Приблизительная оценка: 1 токен ≈ 4 символа для русского текста
        """
        return len(text) // 4

    def add_tokens_used(self, tokens: int):
        """Добавить использованные токены к счетчику"""
        self.total_tokens_today += tokens
        logger.debug(f"Tokens used today: {self.total_tokens_today}/{self.TOTAL_DAILY_BUDGET}")

    def is_blacklisted(self, user_id: int) -> tuple[bool, Optional[str]]:
        """Проверка черного списка"""
        if user_id in self.blacklist:
            logger.warning(f"Blacklisted user attempted access: {user_id}")
            return True, "Доступ заблокирован. Свяжитесь с нашей командой для разблокировки."
        return False, None

    def add_to_blacklist(self, user_id: int, reason: str = "Suspicious activity"):
        """Добавить пользователя в черный список"""
        self.blacklist.add(user_id)
        logger.warning(f"User {user_id} added to blacklist. Reason: {reason}")

    def remove_from_blacklist(self, user_id: int):
        """Убрать пользователя из черного списка"""
        if user_id in self.blacklist:
            self.blacklist.remove(user_id)
            logger.info(f"User {user_id} removed from blacklist")

    def detect_suspicious_activity(self, user_id: int, message: str) -> bool:
        """
        Обнаружение подозрительной активности

        Признаки атаки:
        - Очень длинные сообщения
        - Повторяющиеся сообщения
        - Бессмысленный спам
        """
        is_suspicious = False

        # Проверка 1: Слишком длинное сообщение
        if len(message) > self.MAX_MESSAGE_LENGTH * 0.9:
            is_suspicious = True

        # Проверка 2: Повторяющиеся символы (спам)
        if len(set(message)) < 10 and len(message) > 50:
            is_suspicious = True

        # Проверка 3: Только цифры или бессмыслица
        if message.replace(" ", "").isdigit() and len(message) > 100:
            is_suspicious = True

        if is_suspicious:
            self.suspicious_users[user_id] += 1
            logger.warning(f"Suspicious activity detected from user {user_id}. Count: {self.suspicious_users[user_id]}")

            # После 3 подозрительных сообщений - в блэклист
            if self.suspicious_users[user_id] >= 3:
                self.add_to_blacklist(user_id, "Multiple suspicious messages")
                return True

        return is_suspicious

    def check_all_security(self, user_id: int, message: str) -> tuple[bool, Optional[str]]:
        """
        Комплексная проверка всех систем безопасности

        Returns:
            (allowed, reason) - True если все проверки пройдены
        """
        # 1. Проверка черного списка
        is_blocked, reason = self.is_blacklisted(user_id)
        if is_blocked:
            return False, reason

        # 2. Проверка длины сообщения
        is_valid, reason = self.check_message_length(message)
        if not is_valid:
            return False, reason

        # 3. Обнаружение подозрительной активности
        if self.detect_suspicious_activity(user_id, message):
            return False, "Обнаружена подозрительная активность. Доступ заблокирован."

        # 4. Rate limiting
        is_allowed, reason = self.check_rate_limit(user_id)
        if not is_allowed:
            return False, reason

        # 5. Cooldown
        is_allowed, reason = self.check_cooldown(user_id)
        if not is_allowed:
            return False, reason

        # 6. Проверка общего бюджета
        is_allowed, reason = self.check_total_budget()
        if not is_allowed:
            return False, reason

        # Все проверки пройдены!
        return True, None

    def reset_stats_time(self):
        """Сброс времени начала сбора статистики"""
        self.stats_start_time = datetime.now()
        logger.info(f"Stats start time reset to {self.stats_start_time}")

    def get_stats(self) -> Dict:
        """Получить статистику безопасности"""
        return {
            'blacklisted_users': len(self.blacklist),
            'suspicious_users': len(self.suspicious_users),
            'total_tokens_today': self.total_tokens_today,
            'daily_budget': self.TOTAL_DAILY_BUDGET,
            'budget_remaining': self.TOTAL_DAILY_BUDGET - self.total_tokens_today,
            'budget_percentage': (self.total_tokens_today / self.TOTAL_DAILY_BUDGET * 100),
            'stats_start_time': self.stats_start_time,
        }


# Глобальный экземпляр
security_manager = SecurityManager()


if __name__ == '__main__':
    # Тестирование
    logging.basicConfig(level=logging.INFO)

    print("=== Testing Security Manager ===\n")

    # Тест 1: Rate limiting
    print("Test 1: Rate limiting")
    test_user = 999999999

    for i in range(12):
        allowed, reason = security_manager.check_rate_limit(test_user)
        print(f"  Message {i+1}: {'✅ Allowed' if allowed else f'❌ Blocked - {reason}'}")

    # Тест 2: Cooldown
    print("\nTest 2: Cooldown")
    for i in range(3):
        allowed, reason = security_manager.check_cooldown(test_user)
        print(f"  Attempt {i+1}: {'✅ Allowed' if allowed else f'❌ Blocked - {reason}'}")
        time.sleep(1)

    # Тест 3: Подозрительная активность
    print("\nTest 3: Suspicious activity detection")
    spam_messages = [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "111111111111111111111111111111111111111111111111111111111111",
        "sssssssssssssssssssssssssssssssssssssssssssssssssssss",
    ]

    for msg in spam_messages:
        is_suspicious = security_manager.detect_suspicious_activity(test_user, msg)
        print(f"  Message '{msg[:20]}...': {'🚨 Suspicious' if is_suspicious else '✅ OK'}")

    # Тест 4: Статистика
    print("\nTest 4: Statistics")
    stats = security_manager.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
