"""
Channel Moderation Module
Модерация комментариев в Telegram канале @legal_ai_pro.

Функционал:
1. Автоматическая фильтрация спама и запрещенных слов
2. AI анализ тональности комментариев
3. Модерация рекламы и нерелевантного контента
4. Сохранение статистики модерации
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import re

from aiogram import Bot
from aiogram.types import Message

from app.config import settings
from app.models.database import PostComment
from app.modules.llm_provider import get_llm_provider
import structlog

logger = structlog.get_logger()


class ChannelModeration:
    """Модерация комментариев в Telegram канале."""

    def __init__(self):
        self.llm = get_llm_provider()
        self.bot: Optional[Bot] = None

        # Списки запрещенных слов и паттернов
        self.forbidden_words = self._load_forbidden_words()
        self.spam_patterns = self._load_spam_patterns()

        # Статистика модерации
        self.stats = {
            'total_comments': 0,
            'moderated_comments': 0,
            'blocked_comments': 0,
            'spam_detected': 0,
            'off_topic': 0,
            'negative_sentiment': 0
        }

    def set_bot(self, bot: Bot):
        """Установить экземпляр бота для модерации."""
        self.bot = bot

    def _load_forbidden_words(self) -> List[str]:
        """Загрузить список запрещенных слов."""
        return [
            # Реклама и спам
            'купить', 'продать', 'цена', 'скидка', 'акция', 'распродажа',
            'заработать', 'деньги', 'рублей', 'долларов', 'евро',
            'инвестиции', 'прибыль', 'доход',

            # Контакты и ссылки
            'телефон', 'номер', 'контакт', 'связаться', 'написать',
            '@', '.com', '.ru', 'http', 'www',

            # Запрещенные темы
            'политика', 'религия', 'наркотики', 'алкоголь', 'оружие',
            'порно', 'секс', 'эротика', 'мат', 'ругань'
        ]

    def _load_spam_patterns(self) -> List[str]:
        """Загрузить паттерны спама."""
        return [
            r'\b\d{10,}\b',  # Длинные цифры (телефоны)
            r'\+7\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',  # Российские номера
            r'\b\w+@\w+\.\w+\b',  # Email адреса
            r'https?://[^\s]+',  # Ссылки
            r'[A-Z]{5,}',  # Капс лок
            r'[!]{3,}',  # Множественные восклицательные знаки
            r'[?]{3,}',  # Множественные вопросительные знаки
        ]

    async def moderate_comment(self, message: Message, channel_id: str) -> Dict[str, Any]:
        """
        Модерировать комментарий к посту в канале.

        Args:
            message: Сообщение из канала
            channel_id: ID канала

        Returns:
            Словарь с результатом модерации
        """
        self.stats['total_comments'] += 1

        result = {
            'moderated': False,
            'action': 'allow',  # 'allow', 'delete', 'warn'
            'reason': None,
            'confidence': 0.0,
            'sentiment': 'neutral'
        }

        try:
            # 1. Базовая фильтрация спама
            spam_check = self._check_spam(message.text or "")
            if spam_check['is_spam']:
                result.update({
                    'moderated': True,
                    'action': 'delete',
                    'reason': spam_check['reason'],
                    'confidence': spam_check['confidence']
                })
                self.stats['spam_detected'] += 1
                return result

            # 2. Проверка на запрещенные слова
            forbidden_check = self._check_forbidden_words(message.text or "")
            if forbidden_check['has_forbidden']:
                result.update({
                    'moderated': True,
                    'action': 'delete',
                    'reason': forbidden_check['reason'],
                    'confidence': 0.9
                })
                self.stats['blocked_comments'] += 1
                return result

            # 3. AI анализ релевантности и тональности
            ai_analysis = await self._analyze_comment_with_ai(message.text or "")
            result['sentiment'] = ai_analysis['sentiment']

            if ai_analysis['is_off_topic']:
                result.update({
                    'moderated': True,
                    'action': 'warn',
                    'reason': 'Комментарий не по теме LegalTech',
                    'confidence': ai_analysis['confidence']
                })
                self.stats['off_topic'] += 1
            elif ai_analysis['sentiment'] == 'negative' and ai_analysis['confidence'] > 0.7:
                result.update({
                    'moderated': True,
                    'action': 'warn',
                    'reason': 'Негативный комментарий',
                    'confidence': ai_analysis['confidence']
                })
                self.stats['negative_sentiment'] += 1
            else:
                self.stats['moderated_comments'] += 1

        except Exception as e:
            logger.error(f"Error moderating comment: {e}")
            # В случае ошибки пропускаем комментарий
            result['moderated'] = False

        return result

    def _check_spam(self, text: str) -> Dict[str, Any]:
        """Проверить текст на спам."""
        text_lower = text.lower()

        # Проверка запрещенных слов
        for word in self.forbidden_words[:20]:  # Проверяем только ключевые слова спама
            if word in text_lower:
                return {
                    'is_spam': True,
                    'reason': f'Обнаружено запрещенное слово: "{word}"',
                    'confidence': 0.8
                }

        # Проверка паттернов
        for pattern in self.spam_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return {
                    'is_spam': True,
                    'reason': 'Обнаружен спам-шаблон',
                    'confidence': 0.9
                }

        # Проверка на слишком короткие/длинные сообщения
        words_count = len(text.split())
        if words_count < 2 or words_count > 100:
            return {
                'is_spam': True,
                'reason': 'Подозрительная длина сообщения',
                'confidence': 0.6
            }

        return {'is_spam': False, 'reason': None, 'confidence': 0.0}

    def _check_forbidden_words(self, text: str) -> Dict[str, Any]:
        """Проверить на запрещенные слова."""
        text_lower = text.lower()

        for word in self.forbidden_words:
            if word in text_lower:
                return {
                    'has_forbidden': True,
                    'reason': f'Запрещенное слово: "{word}"',
                }

        return {'has_forbidden': False, 'reason': None}

    async def _analyze_comment_with_ai(self, text: str) -> Dict[str, Any]:
        """AI анализ комментария на релевантность и тональность."""
        if not text.strip():
            return {
                'is_off_topic': True,
                'sentiment': 'neutral',
                'confidence': 0.5
            }

        try:
            prompt = f"""
            Проанализируй комментарий к посту о LegalTech (ИИ в юриспруденции).

            Комментарий: "{text}"

            Определи:
            1. Релевантность теме LegalTech (да/нет)
            2. Тональность (positive/negative/neutral)
            3. Уверенность в оценке (0.0-1.0)

            Ответь только в формате JSON:
            {{"is_relevant": true/false, "sentiment": "positive/negative/neutral", "confidence": 0.0-1.0}}
            """

            response = await self.llm.generate_response(
                prompt=prompt,
                max_tokens=100,
                temperature=0.1
            )

            # Парсим JSON из ответа
            import json
            try:
                analysis = json.loads(response.strip())
                return {
                    'is_off_topic': not analysis.get('is_relevant', True),
                    'sentiment': analysis.get('sentiment', 'neutral'),
                    'confidence': analysis.get('confidence', 0.5)
                }
            except json.JSONDecodeError:
                # Fallback на простую логику
                return self._fallback_analysis(text)

        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return self._fallback_analysis(text)

    def _fallback_analysis(self, text: str) -> Dict[str, Any]:
        """Простой анализ без AI (fallback)."""
        text_lower = text.lower()

        # Проверка на LegalTech ключевые слова
        legaltech_keywords = [
            'ии', 'ai', 'legaltech', 'право', 'юрист', 'закон', 'договор',
            'автоматизация', 'нейросеть', 'машинное обучение', 'комплаенс'
        ]

        relevant_words = sum(1 for word in legaltech_keywords if word in text_lower)
        is_relevant = relevant_words >= 1

        # Простая оценка тональности
        positive_words = ['хорошо', 'отлично', 'спасибо', 'интересно', 'полезно', 'круто']
        negative_words = ['плохо', 'ужасно', 'отвратительно', 'бесполезно', 'неправильно']

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            sentiment = 'positive'
        elif negative_count > positive_count:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        return {
            'is_off_topic': not is_relevant,
            'sentiment': sentiment,
            'confidence': 0.6
        }

    async def take_moderation_action(self, message: Message, moderation_result: Dict[str, Any]):
        """
        Выполнить действие модерации.

        Args:
            message: Сообщение для модерации
            moderation_result: Результат анализа модерации
        """
        if not self.bot:
            logger.error("Bot not set for moderation actions")
            return

        try:
            if moderation_result['action'] == 'delete':
                # Удалить сообщение
                await self.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=message.message_id
                )
                logger.info(f"Deleted comment: {moderation_result['reason']}")

            elif moderation_result['action'] == 'warn':
                # Отправить предупреждение
                warning_text = (
                    f"⚠️ <b>Внимание!</b>\n\n"
                    f"{moderation_result['reason']}\n\n"
                    f"<i>Пожалуйста, придерживайтесь темы LegalTech и ИИ в юриспруденции.</i>"
                )
                await self.bot.send_message(
                    chat_id=message.chat.id,
                    text=warning_text,
                    parse_mode="HTML",
                    reply_to_message_id=message.message_id
                )
                logger.info(f"Warned user: {moderation_result['reason']}")

        except Exception as e:
            logger.error(f"Error taking moderation action: {e}")

    def get_moderation_stats(self) -> Dict[str, int]:
        """Получить статистику модерации."""
        return self.stats.copy()

    def reset_stats(self):
        """Сбросить статистику модерации."""
        for key in self.stats:
            self.stats[key] = 0