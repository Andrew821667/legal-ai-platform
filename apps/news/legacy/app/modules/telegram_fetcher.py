"""
Telegram Channel Fetcher Module
Сбор новостей из публичных Telegram каналов через Telegram Client API.

Использует Telethon для подключения к Telegram и чтения сообщений.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.errors import (
    ChannelPrivateError,
    ChannelInvalidError,
    FloodWaitError,
    UsernameInvalidError
)

from app.config import settings
import structlog

logger = structlog.get_logger()


class TelegramChannelFetcher:
    """Сборщик новостей из Telegram каналов."""

    def __init__(self):
        """Инициализация Telegram Client."""
        self.client: Optional[TelegramClient] = None
        self.api_id = settings.telegram_api_id
        self.api_hash = settings.telegram_api_hash
        self.session_name = settings.telegram_session_name

    async def __aenter__(self):
        """Async context manager entry."""
        if not self.api_id or not self.api_hash:
            logger.warning(
                "telegram_api_not_configured",
                message="TELEGRAM_API_ID or TELEGRAM_API_HASH not set, skipping Telegram fetch"
            )
            return self

        # Создаем клиент
        self.client = TelegramClient(
            self.session_name,
            self.api_id,
            self.api_hash
        )

        # Подключаемся
        await self.client.connect()

        # Проверяем авторизацию
        if not await self.client.is_user_authorized():
            logger.warning(
                "telegram_not_authorized",
                message="Telegram session not authorized. Need to authorize first."
            )
            # Для бота не требуется phone number auth для чтения публичных каналов
            # Но нужна начальная авторизация (делается один раз)

        logger.info("telegram_client_connected", session=self.session_name)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            logger.info("telegram_client_disconnected")

    def _is_relevant_article(self, title: str, content: str) -> bool:
        """
        Проверить релевантность статьи по ключевым словам AI + legal.

        Использует ту же логику что и в fetcher.py

        Args:
            title: Заголовок статьи
            content: Содержание статьи

        Returns:
            True если статья релевантна теме AI + юриспруденция/бизнес
        """
        # Объединяем title и content для поиска
        text = f"{title} {content}".lower()

        # Ключевые слова AI (русские и английские)
        ai_keywords = [
            # Русские
            "искусственный интеллект", "ии", "нейросет", "машинное обучение",
            "chatgpt", "gpt", "openai", "claude", "gemini", "llm", "нейронн",
            "автоматизац", "роботизац", "ml ", "ai ", "deep learning",
            # Английские
            "artificial intelligence", "machine learning", "neural network",
            "automation", "robotics", "nlp", "computer vision"
        ]

        # Ключевые слова legal/business (русские и английские)
        legal_business_keywords = [
            # Русские - юридические
            "право", "суд", "юрист", "закон", "договор", "правов", "юридическ",
            "compliance", "комплаенс", "регулиров", "нормативн", "судебн",
            # Русские - бизнес
            "бизнес", "компан", "корпорат", "управлен", "риск", "безопасност",
            "данных", "персональн", "gdpr", "конфиденциальн",
            # Английские
            "legal", "law", "court", "lawyer", "attorney", "contract",
            "regulation", "legaltech", "business", "corporate", "governance",
            "compliance", "risk", "data protection", "privacy"
        ]

        # Проверяем наличие хотя бы одного AI keyword
        has_ai = any(keyword in text for keyword in ai_keywords)

        # Проверяем наличие хотя бы одного legal/business keyword
        has_legal_or_business = any(keyword in text for keyword in legal_business_keywords)

        # Релевантна если есть ai ИЛИ (legal ИЛИ business) - как в RSS fetcher
        is_relevant = has_ai or has_legal_or_business

        if not is_relevant:
            logger.debug(
                "telegram_message_filtered_irrelevant",
                title=title[:100],
                has_ai=has_ai,
                has_legal_or_business=has_legal_or_business
            )

        return is_relevant

    async def fetch_channel_messages(
        self,
        channel_username: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить сообщения из Telegram канала.

        Args:
            channel_username: Username канала (с @ или без)
            limit: Количество сообщений для получения

        Returns:
            Список словарей с данными сообщений
        """
        if not self.client:
            logger.warning("telegram_client_not_initialized")
            return []

        if limit is None:
            limit = settings.telegram_fetch_limit

        articles = []
        filtered_count = 0

        # Убираем @ если есть
        channel_username = channel_username.lstrip('@')

        logger.info(
            "fetching_telegram_channel",
            channel=channel_username,
            limit=limit
        )

        try:
            # Получаем entity канала
            try:
                entity = await self.client.get_entity(channel_username)
            except (ChannelPrivateError, ChannelInvalidError, UsernameInvalidError) as e:
                logger.error(
                    "telegram_channel_access_error",
                    channel=channel_username,
                    error=str(e)
                )
                return articles

            # Получаем последние сообщения
            messages = await self.client.get_messages(entity, limit=limit)

            # Обрабатываем сообщения
            for message in messages:
                if not isinstance(message, Message):
                    continue

                # Пропускаем сообщения без текста
                if not message.text:
                    continue

                # Пропускаем очень старые сообщения (старше 7 дней)
                if message.date:
                    message_date = message.date.replace(tzinfo=None)
                    if message_date < datetime.utcnow() - timedelta(days=7):
                        continue

                # Формируем URL сообщения
                message_url = f"https://t.me/{channel_username}/{message.id}"

                # Используем первую строку как заголовок
                lines = message.text.strip().split('\n')
                title = lines[0][:200] if lines else "Без заголовка"
                content = message.text[:5000]  # Ограничиваем размер

                # 🔍 ФИЛЬТРАЦИЯ: Проверяем релевантность по AI + legal/business
                if not self._is_relevant_article(title, content):
                    filtered_count += 1
                    logger.debug(
                        "telegram_message_filtered",
                        channel=channel_username,
                        message_id=message.id,
                        title=title[:80],
                        reason="not_ai_legal_business"
                    )
                    continue

                # Создаем article data
                article_data = {
                    "url": message_url,
                    "title": title,
                    "content": content,
                    "source_name": f"Telegram: @{channel_username}",
                    "published_at": message.date.replace(tzinfo=None) if message.date else datetime.utcnow(),
                }

                articles.append(article_data)

                logger.info(
                    "telegram_message_fetched",
                    channel=channel_username,
                    message_id=message.id,
                    title=title[:50]
                )

                # Rate limiting - пауза между обработкой сообщений
                await asyncio.sleep(0.1)

            logger.info(
                "telegram_channel_fetch_complete",
                channel=channel_username,
                total_messages=len(messages),
                filtered_out=filtered_count,
                articles_accepted=len(articles)
            )

        except FloodWaitError as e:
            logger.error(
                "telegram_flood_wait",
                channel=channel_username,
                wait_seconds=e.seconds,
                error=str(e)
            )
            # Ждем если Telegram попросил
            await asyncio.sleep(e.seconds)

        except Exception as e:
            logger.error(
                "telegram_channel_fetch_error",
                channel=channel_username,
                error=str(e),
                error_type=type(e).__name__
            )

        return articles

    async def fetch_all_channels(self) -> tuple[Dict[str, int], List[Dict[str, Any]]]:
        """
        Получить сообщения из всех настроенных каналов.

        Returns:
            Tuple (словарь с количеством статей по каналам, список всех статей)
        """
        if not self.client or not settings.telegram_fetch_enabled:
            logger.info("telegram_fetch_disabled")
            return {}, []

        stats = {}
        all_articles = []
        channels = settings.telegram_channels_list

        if not channels:
            logger.warning("telegram_channels_not_configured")
            return stats, all_articles

        logger.info(
            "fetching_all_telegram_channels",
            channels_count=len(channels),
            channels=channels
        )

        for channel in channels:
            try:
                articles = await self.fetch_channel_messages(channel)
                channel_key = f"Telegram: @{channel.lstrip('@')}"
                stats[channel_key] = len(articles)
                all_articles.extend(articles)

                # Rate limiting между каналами - 1 сек
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(
                    "telegram_channel_error",
                    channel=channel,
                    error=str(e)
                )
                stats[f"Telegram: @{channel.lstrip('@')}"] = 0
                continue

        total_articles = len(all_articles)
        logger.info(
            "telegram_fetch_all_complete",
            total_articles=total_articles,
            channels_count=len(stats),
            stats=stats
        )

        return stats, all_articles


async def fetch_telegram_news() -> tuple[Dict[str, int], List[Dict[str, Any]]]:
    """
    Удобная функция для запуска сбора новостей из Telegram каналов.

    Returns:
        Tuple (статистика по каналам, список статей)
    """
    async with TelegramChannelFetcher() as fetcher:
        if not fetcher.client:
            return {}, []

        return await fetcher.fetch_all_channels()
