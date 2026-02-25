"""
News Cleaner Module
Умная очистка с фильтрацией и дедупликацией.

Функционал:
1. Проверка дублей (по URL и похожести заголовков)
2. Базовые фильтры (длина, язык, спам-паттерны)
3. ML-фильтрация (опционально для Phase 2+)
"""

import re
from typing import List, Optional, Set, Tuple
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from Levenshtein import ratio as levenshtein_ratio

from app.config import settings
from app.models.database import RawArticle, log_to_db
import structlog

logger = structlog.get_logger()


# Черный список ключевых слов (спам-паттерны)
SPAM_PATTERNS = [
    r"казино",
    r"casino",
    r"viagra",
    r"купить\s+диплом",
    r"заработок\s+без",
    r"click\s+here",
    r"free\s+money",
    r"win\s+now",
]

# Паттерны для детекции языка (упрощенный подход)
RUSSIAN_PATTERN = re.compile(r'[а-яА-ЯёЁ]')
ENGLISH_PATTERN = re.compile(r'[a-zA-Z]')


class NewsCleaner:
    """Фильтр и дедупликатор новостей."""

    def __init__(self, db_session: AsyncSession):
        """
        Инициализация cleaner.

        Args:
            db_session: Асинхронная сессия базы данных
        """
        self.db = db_session
        self.spam_regex = re.compile('|'.join(SPAM_PATTERNS), re.IGNORECASE)

    async def get_new_articles(self) -> List[RawArticle]:
        """
        Получить все новые статьи для обработки.

        Returns:
            Список новых статей
        """
        result = await self.db.execute(
            select(RawArticle).where(RawArticle.status == 'new')
        )
        return list(result.scalars().all())

    async def cleanup_old_articles(self) -> int:
        """
        Удалить старые статьи из БД (старше 30 дней).

        Returns:
            Количество удаленных статей
        """
        # Удаляем статьи старше 30 дней
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        result = await self.db.execute(
            select(RawArticle).where(
                RawArticle.fetched_at < cutoff_date,
                RawArticle.status.in_(['rejected', 'filtered'])  # Удаляем только обработанные
            )
        )
        old_articles = result.scalars().all()

        count = len(old_articles)

        for article in old_articles:
            await self.db.delete(article)

        await self.db.commit()

        logger.info("old_articles_cleanup", deleted_count=count, cutoff_date=cutoff_date)

        return count

    def _detect_language(self, text: str) -> Optional[str]:
        """
        Определить язык текста (упрощенная версия).

        Args:
            text: Текст для анализа

        Returns:
            'ru', 'en' или None
        """
        if not text:
            return None

        russian_chars = len(RUSSIAN_PATTERN.findall(text))
        english_chars = len(ENGLISH_PATTERN.findall(text))

        # Если >= 30% кириллицы - считаем русским
        if russian_chars > len(text) * 0.3:
            return 'ru'
        # Если >= 30% латиницы - считаем английским
        elif english_chars > len(text) * 0.3:
            return 'en'

        return None

    def _check_spam_patterns(self, text: str) -> bool:
        """
        Проверить текст на спам-паттерны.

        Args:
            text: Текст для проверки

        Returns:
            True если найден спам, False иначе
        """
        if not text:
            return False

        return bool(self.spam_regex.search(text))

    def _check_minimum_length(self, content: str) -> bool:
        """
        Проверить минимальную длину контента.

        Args:
            content: Контент статьи

        Returns:
            True если длина достаточна, False иначе
        """
        if not content:
            return False

        return len(content.strip()) >= settings.cleaner_min_content_length

    def _check_article_age(self, published_at: Optional[datetime]) -> bool:
        """
        Проверить возраст новости (не старше 3 суток).

        Args:
            published_at: Дата публикации статьи

        Returns:
            True если новость свежая (не старше 3 суток), False иначе
        """
        if not published_at:
            # Если дата публикации не указана, считаем новость свежей
            # (она может быть просто добавлена в систему)
            return True

        # Максимальный возраст новости - 3 суток (72 часа)
        max_age = timedelta(days=3)
        now = datetime.utcnow()

        # Вычисляем возраст новости
        age = now - published_at

        # Проверяем, что новость не старше 3 суток
        return age <= max_age

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """
        Вычислить схожесть двух заголовков.

        Args:
            title1: Первый заголовок
            title2: Второй заголовок

        Returns:
            Коэффициент схожести (0.0 - 1.0)
        """
        if not title1 or not title2:
            return 0.0

        # Нормализуем заголовки (lowercase, убираем лишние пробелы)
        t1 = ' '.join(title1.lower().split())
        t2 = ' '.join(title2.lower().split())

        # Используем Levenshtein distance
        return levenshtein_ratio(t1, t2)

    async def find_duplicates(
        self,
        article: RawArticle,
        existing_articles: List[RawArticle]
    ) -> Optional[RawArticle]:
        """
        Найти дубликаты статьи (улучшенная дедупликация).

        Args:
            article: Статья для проверки
            existing_articles: Список существующих статей

        Returns:
            Дубликат или None
        """
        # Фильтруем existing_articles: оставляем только свежие (не старше 7 дней)
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        recent_articles = [
            a for a in existing_articles
            if a.fetched_at and a.fetched_at >= recent_cutoff
        ]

        for existing in recent_articles:
            # Пропускаем саму себя
            if existing.id == article.id:
                continue

            # Проверка по URL (точное совпадение)
            if existing.url == article.url:
                logger.debug(
                    "duplicate_found_by_url",
                    article_id=article.id,
                    duplicate_id=existing.id
                )
                return existing

            # Проверка по схожести заголовков (повышенный порог для более строгой дедупликации)
            similarity = self._calculate_title_similarity(
                article.title,
                existing.title
            )

            # Используем более высокий порог для дедупликации (0.9 вместо 0.85)
            if similarity >= 0.9:
                logger.debug(
                    "duplicate_found_by_title",
                    article_id=article.id,
                    duplicate_id=existing.id,
                    similarity=similarity
                )
                return existing

            # Дополнительная проверка: если первые 100 символов контента совпадают на 90%
            if article.content and existing.content:
                content_snippet_new = article.content[:100].lower().strip()
                content_snippet_existing = existing.content[:100].lower().strip()

                if content_snippet_new and content_snippet_existing:
                    content_similarity = self._calculate_title_similarity(
                        content_snippet_new,
                        content_snippet_existing
                    )

                    if content_similarity >= 0.9:
                        logger.debug(
                            "duplicate_found_by_content",
                            article_id=article.id,
                            duplicate_id=existing.id,
                            content_similarity=content_similarity
                        )
                        return existing

        return None

    async def filter_article(self, article: RawArticle) -> Tuple[bool, Optional[str]]:
        """
        Применить фильтры к статье.

        Args:
            article: Статья для фильтрации

        Returns:
            Tuple (passed: bool, reason: Optional[str])
            - passed: True если статья прошла фильтры
            - reason: Причина отклонения (если есть)
        """
        # 1. Проверка возраста новости (не старше 3 суток)
        if not self._check_article_age(article.published_at):
            age_days = (datetime.utcnow() - article.published_at).days if article.published_at else 0
            return False, f"Article too old: {age_days} days (max 3 days)"

        # 2. Проверка минимальной длины
        if not self._check_minimum_length(article.content):
            return False, f"Content too short: {len(article.content or '')} chars"

        # 3. Проверка языка
        detected_lang = self._detect_language(article.title + " " + (article.content or ""))

        if detected_lang not in settings.cleaner_languages_list:
            return False, f"Unsupported language: {detected_lang}"

        # 4. Проверка на спам
        combined_text = f"{article.title} {article.content or ''}"
        if self._check_spam_patterns(combined_text):
            return False, "Spam patterns detected"

        # 5. Проверка на наличие ключевых слов (базовая релевантность)
        relevant_keywords = [
            # Русские
            "искусственный интеллект", "ии", "ai", "нейросет",
            "машинное обучение", "автоматизация",
            "право", "юрист", "суд", "закон", "юридическ",
            # Английские
            "artificial intelligence", "machine learning",
            "automation", "law", "legal", "court", "lawyer",
        ]

        text_lower = combined_text.lower()
        has_relevant_keyword = any(
            keyword in text_lower for keyword in relevant_keywords
        )

        if not has_relevant_keyword:
            return False, "No relevant keywords found"

        # Все проверки пройдены
        return True, None

    async def process_articles(self) -> dict:
        """
        Обработать все новые статьи.

        Returns:
            Статистика обработки
        """
        stats = {
            "total": 0,
            "filtered": 0,
            "duplicates": 0,
            "rejected": 0,
            "errors": 0
        }

        # Очищаем старые статьи перед обработкой новых
        cleanup_count = await self.cleanup_old_articles()
        logger.info("old_articles_cleaned", count=cleanup_count)

        # Получаем новые статьи
        new_articles = await self.get_new_articles()
        stats["total"] = len(new_articles)

        if not new_articles:
            logger.info("no_new_articles_to_process")
            return stats

        logger.info("processing_articles", count=len(new_articles))

        # Получаем все существующие статьи для проверки дубликатов
        result = await self.db.execute(
            select(RawArticle).where(RawArticle.status.in_(['filtered', 'processed']))
        )
        existing_articles = list(result.scalars().all())

        for article in new_articles:
            try:
                # 1. Проверка на дубликаты
                duplicate = await self.find_duplicates(article, existing_articles)
                if duplicate:
                    article.status = 'rejected'
                    stats["duplicates"] += 1
                    logger.info(
                        "article_rejected_duplicate",
                        article_id=article.id,
                        title=article.title[:50],
                        duplicate_id=duplicate.id
                    )
                    continue

                # 2. Применение фильтров
                passed, reason = await self.filter_article(article)

                if passed:
                    article.status = 'filtered'
                    article.relevance_score = 1.0  # Базовая оценка, улучшится с ML
                    stats["filtered"] += 1
                    # Добавляем к списку существующих для последующих проверок
                    existing_articles.append(article)

                    logger.info(
                        "article_filtered",
                        article_id=article.id,
                        title=article.title[:50]
                    )
                else:
                    article.status = 'rejected'
                    stats["rejected"] += 1
                    logger.info(
                        "article_rejected",
                        article_id=article.id,
                        title=article.title[:50],
                        reason=reason
                    )

            except Exception as e:
                stats["errors"] += 1
                logger.error(
                    "article_processing_error",
                    article_id=article.id,
                    error=str(e)
                )
                continue

        # Сохраняем изменения
        await self.db.commit()

        # Логируем статистику
        await log_to_db(
            "INFO",
            f"Cleaning completed: {stats['filtered']} filtered, {stats['rejected']} rejected",
            stats,
            session=self.db  # Передаём существующую сессию
        )

        logger.info("cleaning_complete", **stats)

        return stats

    async def mark_as_rejected(self, article_id: int, reason: str) -> bool:
        """
        Пометить статью как отклоненную.

        Args:
            article_id: ID статьи
            reason: Причина отклонения

        Returns:
            True если успешно, False иначе
        """
        try:
            await self.db.execute(
                update(RawArticle)
                .where(RawArticle.id == article_id)
                .values(status='rejected')
            )
            await self.db.commit()

            logger.info(
                "article_marked_rejected",
                article_id=article_id,
                reason=reason
            )

            return True

        except Exception as e:
            logger.error(
                "mark_rejected_error",
                article_id=article_id,
                error=str(e)
            )
            return False


# ML-фильтрация (опционально для Phase 2+)
class MLClassifier:
    """
    Zero-shot классификатор для фильтрации новостей.

    Будет реализован в Phase 2 с использованием HuggingFace transformers.
    """

    def __init__(self):
        """Инициализация классификатора."""
        self.model = None
        self.enabled = False  # Будет включено в Phase 2

    async def classify(self, text: str) -> Tuple[str, float]:
        """
        Классифицировать текст.

        Args:
            text: Текст для классификации

        Returns:
            Tuple (label, confidence)
        """
        # TODO: Реализовать в Phase 2
        # from transformers import pipeline
        # classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        # result = classifier(text, candidate_labels=settings.ml_labels_list)
        # return result['labels'][0], result['scores'][0]

        return "legal AI news", 1.0  # Заглушка для MVP


async def clean_news(db_session: AsyncSession) -> dict:
    """
    Удобная функция для запуска очистки новостей.

    Args:
        db_session: Асинхронная сессия БД

    Returns:
        Статистика очистки
    """
    cleaner = NewsCleaner(db_session)
    return await cleaner.process_articles()
