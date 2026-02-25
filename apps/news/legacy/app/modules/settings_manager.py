"""
Settings Manager - управление системными настройками через БД.
Все настройки хранятся в таблице system_settings и могут быть изменены через UI.
"""

import json
from typing import Any, Optional, Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import SystemSettings
import structlog

logger = structlog.get_logger()


# ====================
# Default Settings
# ====================

DEFAULT_SETTINGS = {
    # Источники новостей
    "sources.google_news_ru.enabled": {"value": True, "type": "bool", "category": "sources", "description": "Google News RSS (RU)"},
    "sources.google_news_en.enabled": {"value": True, "type": "bool", "category": "sources", "description": "Google News RSS (EN)"},
    "sources.google_news_rss_ru.enabled": {"value": True, "type": "bool", "category": "sources", "description": "Google News RU"},
    "sources.google_news_rss_en.enabled": {"value": True, "type": "bool", "category": "sources", "description": "Google News EN"},
    "sources.habr.enabled": {"value": True, "type": "bool", "category": "sources", "description": "Habr - Новости"},
    "sources.perplexity_ru.enabled": {"value": True, "type": "bool", "category": "sources", "description": "Perplexity Search (RU)"},
    "sources.perplexity_en.enabled": {"value": True, "type": "bool", "category": "sources", "description": "Perplexity Search (EN)"},
    "sources.telegram_channels.enabled": {"value": True, "type": "bool", "category": "sources", "description": "Telegram Channels"},
    "sources.interfax.enabled": {"value": True, "type": "bool", "category": "sources", "description": "Interfax - Наука и технологии"},
    "sources.lenta.enabled": {"value": True, "type": "bool", "category": "sources", "description": "Lenta.ru - Технологии"},
    "sources.rbc.enabled": {"value": True, "type": "bool", "category": "sources", "description": "RBC - Технологии"},
    "sources.tass.enabled": {"value": True, "type": "bool", "category": "sources", "description": "TASS - Наука и технологии"},

    # Провайдер LLM
    "llm.provider": {"value": "deepseek", "type": "string", "category": "llm", "description": "LLM провайдер (openai/perplexity/deepseek)"},

    # Модели LLM (оптимизировано для снижения расходов)
    "llm.analysis.model": {"value": "deepseek-chat", "type": "string", "category": "llm", "description": "Модель для AI анализа"},
    "llm.draft_generation.model": {"value": "deepseek-chat", "type": "string", "category": "llm", "description": "Модель для генерации драфтов"},
    "llm.ranking.model": {"value": "deepseek-chat", "type": "string", "category": "llm", "description": "Модель для ranking статей"},

    # DALL-E генерация
    "dalle.enabled": {"value": False, "type": "bool", "category": "media", "description": "Включить DALL-E генерацию"},
    "dalle.model": {"value": "dall-e-3", "type": "string", "category": "media", "description": "Модель DALL-E"},
    "dalle.quality": {"value": "standard", "type": "string", "category": "media", "description": "Качество (standard/hd)"},
    "dalle.size": {"value": "1024x1024", "type": "string", "category": "media", "description": "Размер изображения"},
    "dalle.auto_generate": {"value": False, "type": "bool", "category": "media", "description": "Автоматически для всех постов"},
    "dalle.ask_on_review": {"value": True, "type": "bool", "category": "media", "description": "Спрашивать при модерации"},

    # Автопубликация
    "auto_publish.enabled": {"value": False, "type": "bool", "category": "publishing", "description": "Включить автопубликацию"},
    "auto_publish.mode": {"value": "best_time", "type": "string", "category": "publishing", "description": "Режим: best_time/scheduled"},
    "auto_publish.max_per_day": {"value": 3, "type": "int", "category": "publishing", "description": "Максимум постов в день"},
    "auto_publish.weekdays_only": {"value": False, "type": "bool", "category": "publishing", "description": "Только будни"},
    "auto_publish.skip_holidays": {"value": False, "type": "bool", "category": "publishing", "description": "Пропускать праздники"},

    # Настройки сбора новостей
    "fetcher.max_articles_per_source": {"value": 10, "type": "int", "category": "fetcher", "description": "Максимум статей на источник (снижено для экономии)"},


    # Фильтрация контента
    "filtering.min_score": {"value": 0.6, "type": "float", "category": "quality", "description": "Минимальный скор качества (0-1)"},
    "filtering.min_content_length": {"value": 300, "type": "int", "category": "quality", "description": "Минимальная длина текста"},
    "filtering.similarity_threshold": {"value": 0.85, "type": "float", "category": "quality", "description": "Порог схожести (0-1)"},

    # Бюджет API (50 рублей = ~0.55 USD при курсе 90 руб/$)
    "budget.max_per_month": {"value": 0.6, "type": "float", "category": "budget", "description": "Максимум USD в месяц (~50 руб)"},
    "budget.warning_threshold": {"value": 0.5, "type": "float", "category": "budget", "description": "Порог предупреждения"},
    "budget.stop_on_exceed": {"value": True, "type": "bool", "category": "budget", "description": "Останавливать при превышении"},
    "budget.switch_to_cheap": {"value": True, "type": "bool", "category": "budget", "description": "Переходить на дешевые модели"},
}


# ====================
# Helper Functions
# ====================

def _serialize_value(value: Any, value_type: str) -> str:
    """Сериализация значения в строку для хранения в БД."""
    if value_type == "bool":
        return "true" if value else "false"
    elif value_type == "int":
        return str(int(value))
    elif value_type == "float":
        return str(float(value))
    else:  # string
        return str(value)


def _deserialize_value(value_str: str, value_type: str) -> Any:
    """Десериализация значения из строки."""
    if value_type == "bool":
        return value_str.lower() == "true"
    elif value_type == "int":
        return int(value_str)
    elif value_type == "float":
        return float(value_str)
    else:  # string
        return value_str


# ====================
# Public API
# ====================

async def get_setting(key: str, db: AsyncSession, default: Any = None) -> Any:
    """
    Получить значение настройки по ключу.

    Args:
        key: Ключ настройки
        db: Сессия БД
        default: Значение по умолчанию

    Returns:
        Значение настройки
    """
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting:
        return _deserialize_value(setting.value, setting.type)
    else:
        logger.warning("setting_not_found", key=key, using_default=default)
        return default


async def set_setting(key: str, value: Any, db: AsyncSession) -> None:
    """
    Установить значение настройки.

    Args:
        key: Ключ настройки
        db: Сессия БД
        value: Новое значение
    """
    # Находим существующую настройку
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting:
        # Обновляем существующую
        setting_config = DEFAULT_SETTINGS.get(key, {})
        value_type = setting_config.get("type", "string")

        setting.value = _serialize_value(value, value_type)
        setting.updated_at = None  # Автообновление
        logger.info("setting_updated", key=key, value=value)
    else:
        # Создаем новую
        setting_config = DEFAULT_SETTINGS.get(key, {})
        value_type = setting_config.get("type", "string")

        new_setting = SystemSettings(
            key=key,
            value=_serialize_value(value, value_type),
            type=value_type,
            category=setting_config.get("category", "general"),
            description=setting_config.get("description", "")
        )
        db.add(new_setting)
        logger.info("setting_created", key=key, value=value)

    # ВАЖНО: Сохраняем изменения в БД
    await db.commit()


async def get_category_settings(category: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Получить все настройки категории.

    Args:
        category: Название категории

    Returns:
        Словарь с настройками категории
    """
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.category == category)
    )
    settings = result.scalars().all()

    result = {}
    for setting in settings:
        result[setting.key] = _deserialize_value(setting.value, setting.type)

    return result


async def init_default_settings(db: AsyncSession) -> None:
    """
    Инициализация дефолтных настроек в БД (если их еще нет).
    Вызывается при старте приложения.
    """
    for key, config in DEFAULT_SETTINGS.items():
        # Проверяем существует ли настройка
        result = await db.execute(
            select(SystemSettings).where(SystemSettings.key == key)
        )
        existing = result.scalar_one_or_none()

        if not existing:
            # Создаём новую настройку
            value_str = _serialize_value(config["value"], config["type"])

            setting = SystemSettings(
                key=key,
                value=value_str,
                type=config["type"],
                category=config["category"],
                description=config["description"]
            )
            db.add(setting)
            logger.info("default_setting_created", key=key, value=config["value"])

    await db.commit()
    logger.info("default_settings_initialized", count=len(DEFAULT_SETTINGS))


async def get_enabled_sources(db: AsyncSession) -> List[str]:
    """Получить список включенных источников."""
    sources = await get_category_settings("sources", db)

    enabled = []
    for key, value in sources.items():
        if value and key.endswith(".enabled"):
            # Извлекаем название источника из ключа
            # sources.google_news_ru.enabled -> google_news_ru
            source_name = key.replace("sources.", "").replace(".enabled", "")
            enabled.append(source_name)

    return enabled



async def is_source_enabled(source_name: str, db: AsyncSession) -> bool:
    """
    Проверить, включен ли конкретный источник.

    Args:
        source_name: Название источника (например, "google_news_ru")
        db: Сессия базы данных

    Returns:
        True если источник включен, False иначе
    """
    key = f"sources.{source_name}.enabled"
    return await get_setting(key, db, default=True)  # По умолчанию True для обратной совместимости

async def get_auto_publish_config(db: AsyncSession) -> Dict[str, Any]:
    """
    Получить конфигурацию автопубликации.

    Args:
        db: Сессия базы данных

    Returns:
        Словарь с настройками автопубликации (без префикса в ключах)
    """
    settings = await get_category_settings("publishing", db)
    # Преобразуем ключи: auto_publish.enabled -> enabled
    result = {}
    for key, value in settings.items():
        if key.startswith("auto_publish."):
            short_key = key.replace("auto_publish.", "")
            result[short_key] = value
    return result

async def get_dalle_config(db: AsyncSession) -> Dict[str, Any]:
    """
    Получить конфигурацию DALL-E генерации изображений.

    Args:
        db: Сессия базы данных

    Returns:
        Словарь с настройками DALL-E (без префикса в ключах)
    """
    settings = await get_category_settings("media", db)
    # Преобразуем ключи: dalle.enabled -> enabled
    result = {}
    for key, value in settings.items():
        if key.startswith("dalle."):
            short_key = key.replace("dalle.", "")
            result[short_key] = value
    return result

