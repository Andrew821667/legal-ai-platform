#!/usr/bin/env python3
"""
Конфигурация бота
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class Config:
    """Класс конфигурации"""

    def __init__(self):
        # Telegram Bot Token
        self.TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")

        # OpenAI API Key
        self.OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY')
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не установлен в переменных окружения")

        # Admin Telegram ID
        admin_id = os.getenv('ADMIN_TELEGRAM_ID')
        if not admin_id:
            raise ValueError("ADMIN_TELEGRAM_ID не установлен в переменных окружения")
        self.ADMIN_TELEGRAM_ID: int = int(admin_id)

        # Настройки AI
        self.AI_MODEL: str = os.getenv('AI_MODEL', 'gpt-4o-mini')
        self.OPENAI_MODEL: str = self.AI_MODEL  # Для обратной совместимости
        self.MAX_TOKENS: int = int(os.getenv('MAX_TOKENS', '1000'))
        self.MAX_COMPLETION_TOKENS: int = self.MAX_TOKENS  # Для обратной совместимости
        self.TEMPERATURE: float = float(os.getenv('TEMPERATURE', '0.7'))
        self.MAX_HISTORY_MESSAGES: int = int(os.getenv('MAX_HISTORY_MESSAGES', '10'))
        self.RESPONSE_DELAY: float = float(os.getenv('RESPONSE_DELAY', '0.0'))

        # Настройки базы данных
        self.DB_PATH: str = os.getenv('DB_PATH', 'data/bot.db')
        self.DATABASE_PATH: str = self.DB_PATH  # Для обратной совместимости

        # Настройки логирования
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FILE: str = os.getenv('LOG_FILE', 'logs/bot.log')

        # Настройки квалификации лидов
        self.LEAD_QUALIFICATION_THRESHOLD: float = float(os.getenv('LEAD_QUALIFICATION_THRESHOLD', '0.7'))

        # Настройки безопасности
        self.MAX_MESSAGE_LENGTH: int = int(os.getenv('MAX_MESSAGE_LENGTH', '4096'))
        self.RATE_LIMIT_REQUESTS: int = int(os.getenv('RATE_LIMIT_REQUESTS', '10'))
        self.RATE_LIMIT_WINDOW: int = int(os.getenv('RATE_LIMIT_WINDOW', '60'))  # секунды

        # Настройки email/SMTP
        self.SMTP_SERVER: str = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.SMTP_PORT: int = int(os.getenv('SMTP_PORT', '587'))
        self.SMTP_USER: str = os.getenv('SMTP_USER', '')
        self.SMTP_PASSWORD: str = os.getenv('SMTP_PASSWORD', '')
        self.FROM_EMAIL: str = os.getenv('FROM_EMAIL', '')
        self.FROM_NAME: str = os.getenv('FROM_NAME', 'Legal AI Bot')

    def validate(self):
        """Валидация конфигурации"""
        required_fields = [
            'TELEGRAM_BOT_TOKEN',
            'OPENAI_API_KEY',
            'ADMIN_TELEGRAM_ID'
        ]

        missing_fields = []
        for field in required_fields:
            value = getattr(self, field)
            if not value:
                missing_fields.append(field)

        if missing_fields:
            raise ValueError(f"Отсутствуют обязательные поля: {', '.join(missing_fields)}")

        # Проверка формата токенов
        if not self.TELEGRAM_BOT_TOKEN.startswith(('bot', '123456:ABC-')):
            raise ValueError("Неверный формат TELEGRAM_BOT_TOKEN")

        if not self.OPENAI_API_KEY.startswith(('sk-', 'sk-proj-')):
            raise ValueError("Неверный формат OPENAI_API_KEY")

        return True