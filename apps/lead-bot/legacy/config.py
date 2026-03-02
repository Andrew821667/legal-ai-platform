#!/usr/bin/env python3
"""
Конфигурация бота
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения детерминированно:
# 1) сначала локальный .env этого бота (приоритетный),
# 2) затем корневой .env репозитория как fallback для недостающих ключей.
_THIS_DIR = Path(__file__).resolve().parent
_LOCAL_ENV = _THIS_DIR / ".env"
_ROOT_ENV = _THIS_DIR.parents[2] / ".env"

if _LOCAL_ENV.exists():
    load_dotenv(_LOCAL_ENV, override=False)
if _ROOT_ENV.exists():
    load_dotenv(_ROOT_ENV, override=False)

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
        self.OPENAI_BASE_URL: str = os.getenv('OPENAI_BASE_URL', '').strip()

        # Admin Telegram ID
        admin_id = os.getenv('ADMIN_TELEGRAM_ID')
        if not admin_id:
            raise ValueError("ADMIN_TELEGRAM_ID не установлен в переменных окружения")
        self.ADMIN_TELEGRAM_ID: int = int(admin_id)

        # Настройки AI
        # Поддерживаем оба имени переменной для обратной совместимости:
        # AI_MODEL и OPENAI_MODEL.
        self.AI_MODEL: str = os.getenv('AI_MODEL') or os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.OPENAI_MODEL: str = self.AI_MODEL
        self.MAX_TOKENS: int = int(os.getenv('MAX_TOKENS', '1000'))
        self.MAX_COMPLETION_TOKENS: int = int(os.getenv('MAX_COMPLETION_TOKENS', str(self.MAX_TOKENS)))
        self.TEMPERATURE: float = float(os.getenv('TEMPERATURE', '0.7'))
        self.MAX_HISTORY_MESSAGES: int = int(os.getenv('MAX_HISTORY_MESSAGES', '10'))
        self.RESPONSE_DELAY: float = float(os.getenv('RESPONSE_DELAY', '0.0'))
        self.LLM_TIMEOUT_SECONDS: float = float(os.getenv('LLM_TIMEOUT_SECONDS', '25'))
        self.LLM_MAX_RETRIES: int = int(os.getenv('LLM_MAX_RETRIES', '1'))
        self.STREAMING_PREVIEW: bool = os.getenv('STREAMING_PREVIEW', '0').strip().lower() in {'1', 'true', 'yes'}

        # Настройки базы данных
        self.DB_PATH: str = os.getenv('DB_PATH') or os.getenv('DATABASE_PATH', 'data/bot.db')
        self.DATABASE_PATH: str = self.DB_PATH

        # Настройки логирования
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FILE: str = os.getenv('LOG_FILE', 'logs/bot.log')

        # Куда отправлять уведомления по лидам (если не задано — админу).
        leads_chat_id = os.getenv('LEADS_CHAT_ID', '').strip()
        self.LEADS_CHAT_ID: Optional[int] = int(leads_chat_id) if leads_chat_id else None
        self.ALLOW_ADMIN_TEST_LEADS: bool = os.getenv('ALLOW_ADMIN_TEST_LEADS', '1').strip().lower() in {'1', 'true', 'yes'}
        modules_raw = os.getenv('AVAILABLE_SERVICE_MODULES', '').strip()
        self.AVAILABLE_SERVICE_MODULES: list[str] = [item.strip() for item in modules_raw.split(',') if item.strip()]

        # Compliance / документы
        self.PRIVACY_POLICY_URL: str = os.getenv('PRIVACY_POLICY_URL', 'https://legalaipro.ru/privacy')
        self.TRANSBORDER_CONSENT_URL: str = os.getenv(
            'TRANSBORDER_CONSENT_URL',
            'https://legalaipro.ru/transborder-consent',
        )
        self.USER_AGREEMENT_URL: str = os.getenv('USER_AGREEMENT_URL', 'https://legalaipro.ru/user-agreement')
        self.AI_POLICY_URL: str = os.getenv('AI_POLICY_URL', 'https://legalaipro.ru/ai-policy')
        self.MARKETING_CONSENT_URL: str = os.getenv(
            'MARKETING_CONSENT_URL',
            'https://legalaipro.ru/marketing-consent',
        )
        self.PRIVACY_CONTACT_EMAIL: str = os.getenv('PRIVACY_CONTACT_EMAIL', 'privacy@legalaipro.ru')

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
