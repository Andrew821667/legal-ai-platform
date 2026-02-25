"""
News Fetcher Module
Легальный сбор контента из проверенных источников.

Источники:
1. Google News RSS (русский и английский)
2. Официальные RSS источники
3. Telegram каналы (только через официальный экспорт)
"""

import asyncio
import random
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode, quote_plus

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.settings_manager import get_setting
from app.models.database import RawArticle, Source, log_to_db
import structlog

logger = structlog.get_logger()

# Ключевые слова для предварительной фильтрации статей
RELEVANT_KEYWORDS = {
    # AI и машинное обучение
    'ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning', 'neural network',
    'нейросеть', 'искусственный интеллект', 'машинное обучение', 'глубокое обучение',

    # Юридические технологии
    'legal tech', 'legal technology', 'law tech', 'правовые технологии', 'юридические технологии',
    'legal ai', 'юридический ai', 'правовой ai',

    # Бизнес и стартапы
    'startup', 'стартап', 'business', 'бизнес', 'entrepreneurship', 'предпринимательство',
    'venture capital', 'венчурный капитал', 'инвестиции', 'investment',

    # Технологии
    'technology', 'технология', 'innovation', 'инновации', 'digital transformation',
    'цифровая трансформация', 'automation', 'автоматизация',

    # Финтех и регуляции
    'fintech', 'финтех', 'regulation', 'регулирование', 'compliance', 'комплаенс',
    'blockchain', 'блокчейн', 'cryptocurrency', 'криптовалюта'
}


# User-Agent ротация для легального скрапинга
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


def is_content_valid(content: str, title: str = "") -> bool:
    """
    Валидация контента статьи для защиты от мусора.

    Проверяет:
    - Минимальную длину
    - Отсутствие мусора (языковых меню, навигации)
    - Качество текста

    Args:
        content: Контент статьи
        title: Заголовок статьи (опционально)

    Returns:
        True если контент валидный, False если мусор
    """
    # Минимум 50 символов (RSS summary обычно короче полного контента)
    if not content or len(content.strip()) < 50:
        logger.warning("content_validation_failed", reason="too_short", length=len(content or ""))
        return False

    # Признаки мусора: языковые меню, навигация
    garbage_patterns = [
        'deutsch english español français',  # Меню языков Google
        'united states united kingdom',       # Меню стран
        'all languages afrikaans',            # Список всех языков
        'select your language',               # Выбор языка
        'choose language',                    # Выбор языка
        'language menu',                      # Меню языка
    ]

    # Нормализуем контент: переносы строк -> пробелы, множественные пробелы -> одиночные
    import re
    content_normalized = re.sub(r'\s+', ' ', content.lower()[:500])

    for pattern in garbage_patterns:
        if pattern in content_normalized:
            logger.warning(
                "content_validation_failed",
                reason="garbage_pattern",
                pattern=pattern,
                title=title[:80]
            )
            return False

    # RSS summary могут быть короткими - это нормально
    # Не проверяем минимальное количество слов для RSS feeds

    # Проверка на чрезмерное количество коротких слов (признак мусора)
    words = content.split()
    if len(words) >= 20:  # Проверяем только если достаточно слов
        short_words = [w for w in words[:100] if len(w) <= 3]
        if len(short_words) > len(words[:100]) * 0.7:  # Больше 70% коротких слов = мусор
            logger.warning("content_validation_failed", reason="too_many_short_words", ratio=len(short_words)/len(words[:100]))
            return False

    logger.debug("content_validation_passed", length=len(content), words=len(words))
    return True


def is_article_relevant(title: str, content: str = "") -> bool:
    """
    Проверяет, содержит ли статья релевантные ключевые слова.

    Args:
        title: Заголовок статьи
        content: Содержимое статьи (опционально)

    Returns:
        True если статья содержит релевантные ключевые слова
    """
    text_to_check = f"{title} {content}".lower()

    for keyword in RELEVANT_KEYWORDS:
        if keyword.lower() in text_to_check:
            logger.debug("article_relevant", keyword=keyword, title=title[:50])
            return True

    logger.debug("article_irrelevant", title=title[:50])
    return False


class NewsFetcher:
    """Сборщик новостей из различных источников."""

    def __init__(self, db_session: AsyncSession):
        """
        Инициализация fetcher.

        Args:
            db_session: Асинхронная сессия базы данных
        """
        self.db = db_session
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=settings.fetcher_request_timeout,
            follow_redirects=True,
            headers={"User-Agent": self._get_random_user_agent()}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    def _get_random_user_agent(self) -> str:
        """Получить случайный User-Agent для ротации."""
        return random.choice(USER_AGENTS)

    async def _fetch_with_retry(
        self,
        url: str,
        max_retries: Optional[int] = None
    ) -> Optional[str]:
        """
        Получить контент с retry механизмом.

        Args:
            url: URL для запроса
            max_retries: Максимальное количество попыток

        Returns:
            Контент страницы или None при ошибке
        """
        if max_retries is None:
            max_retries = settings.fetcher_max_retries

        for attempt in range(max_retries):
            try:
                # Rate limiting - 1 запрос в секунду
                if attempt > 0:
                    delay = settings.fetcher_retry_delay * (2 ** attempt)  # Exponential backoff
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(1)  # Base rate limit

                # Обновляем User-Agent для каждой попытки
                self.client.headers["User-Agent"] = self._get_random_user_agent()

                response = await self.client.get(url)
                response.raise_for_status()

                logger.info(
                    "fetch_success",
                    url=url,
                    status_code=response.status_code,
                    attempt=attempt + 1
                )

                return response.text

            except httpx.HTTPError as e:
                logger.warning(
                    "fetch_error",
                    url=url,
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries
                )

                if attempt == max_retries - 1:
                    logger.error(
                        "fetch_failed",
                        url=url,
                        error=str(e),
                        total_attempts=max_retries
                    )
                    await log_to_db(
                        "ERROR",
                        f"Failed to fetch URL after {max_retries} attempts",
                        {"url": url, "error": str(e)},
                        session=self.db  # Передаём существующую сессию
                    )
                    return None

        return None

    def _build_google_news_rss_url(
        self,
        query: str,
        lang: str = "ru",
        region: str = "RU"
    ) -> str:
        """
        Построить URL для Google News RSS.

        Args:
            query: Поисковый запрос
            lang: Язык (ru, en)
            region: Регион (RU, US)

        Returns:
            URL для RSS feed
        """
        params = {
            "q": query,
            "hl": lang,
            "gl": region,
            "ceid": f"{region}:{lang}"
        }
        return f"{settings.google_news_rss_url}?{urlencode(params, quote_via=quote_plus)}"

    async def fetch_google_news_rss(self, lang: str = "ru") -> List[Dict[str, Any]]:
        """
        Получить новости из Google News RSS.

        Args:
            lang: Язык новостей (ru или en)

        Returns:
            Список словарей с новостями
        """
        articles = []

        # Определяем запрос и регион в зависимости от языка
        if lang == "ru":
            query = settings.google_news_query_ru
            region = settings.google_news_region
        else:
            query = settings.google_news_query_en
            region = "US"

        rss_url = self._build_google_news_rss_url(query, lang, region)

        logger.info("fetching_google_news", lang=lang, url=rss_url)

        # Получаем RSS feed
        content = await self._fetch_with_retry(rss_url)
        if not content:
            return articles

        # Парсим RSS
        feed = feedparser.parse(content)

        # Получаем лимит статей из настроек
        max_articles = await get_setting("fetcher.max_articles_per_source", self.db, 300)

        for entry in feed.entries[:max_articles]:
            try:
                # Извлекаем данные из RSS entry
                article_data = {
                    "url": entry.link,
                    "title": entry.title,
                    "content": entry.get("summary", ""),
                    "source_name": f"Google News RSS ({lang.upper()})",
                    "published_at": self._parse_date(entry.get("published")),
                }

                # ОТКЛЮЧЕНО: Google News перенаправляет на consent.google.com
                # Используем только краткое содержание из RSS вместо полного контента
                # full_content = await self._fetch_article_content(entry.link)
                # if full_content:
                #     article_data["content"] = full_content

                articles.append(article_data)

                logger.info(
                    "article_fetched",
                    source="google_news",
                    lang=lang,
                    title=article_data["title"][:50]
                )

            except Exception as e:
                logger.error(
                    "article_parse_error",
                    error=str(e),
                    entry_title=entry.get("title", "Unknown")
                )
                continue

        logger.info(
            "google_news_fetch_complete",
            lang=lang,
            articles_count=len(articles)
        )

        return articles

    async def _fetch_article_content(self, url: str) -> Optional[str]:
        """
        Получить полный текст статьи со страницы.

        Args:
            url: URL статьи

        Returns:
            Текст статьи или None
        """
        try:
            content = await self._fetch_with_retry(url)
            if not content:
                return None

            # Парсим HTML с помощью BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")

            # Удаляем скрипты и стили
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Пытаемся найти основной контент
            # Ищем по распространенным тегам для статей
            article_tags = [
                soup.find("article"),
                soup.find("div", class_=lambda x: x and "content" in x.lower()),
                soup.find("div", class_=lambda x: x and "article" in x.lower()),
                soup.find("main"),
            ]

            for tag in article_tags:
                if tag:
                    # Извлекаем текст
                    text = tag.get_text(separator="\n", strip=True)
                    # Очищаем от лишних пробелов и переносов
                    text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
                    if len(text) > 200:  # Минимальная длина для валидного контента
                        return text[:5000]  # Ограничиваем размер

            # Если не нашли специфичные теги, берем весь body
            body = soup.find("body")
            if body:
                text = body.get_text(separator="\n", strip=True)
                text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
                return text[:5000]

        except Exception as e:
            logger.warning(
                "content_fetch_error",
                url=url,
                error=str(e)
            )

        return None

    def _is_relevant_article(self, title: str, content: str) -> bool:
        """
        Проверить релевантность статьи по ключевым словам AI + legal.

        Args:
            title: Заголовок статьи
            content: Содержание статьи

        Returns:
            True если статья релевантна теме AI + юриспруденция/бизнес
        """
        # Объединяем title и content для поиска
        text = f"{title} {content}".lower()

        # Ключевые слова AI (русские и английские) - разные падежи
        ai_keywords = [
            # Русские - разные падежи
            "искусственный интеллект", "искусственного интеллекта", "искусственным интеллектом",
            "искусственному интеллекту", "искусственном интеллекте",
            "ии", "нейросет", "нейронн", "машинное обучение", "машинного обучения",
            "chatgpt", "gpt", "openai", "claude", "gemini", "llm",
            "автоматизац", "роботизац", "ml ", "ai ", "deep learning",
            # Английские
            "artificial intelligence", "machine learning", "neural network",
            "automation", "robotics", "nlp", "computer vision"
        ]

        # Ключевые слова legal/business (русские и английские) - разные падежи
        legal_business_keywords = [
            # Русские - юридические (разные падежи)
            "прав", "суд", "юрист", "закон", "договор",  # "прав" найдет: право, права, правах
            "compliance", "комплаенс", "регулиров", "нормативн", "судебн",
            "авторск",  # авторский, авторское, авторских
            # Русские - бизнес
            "бизнес", "компан", "корпорат", "управлен", "риск", "безопасност",
            "данных", "персональн", "gdpr", "конфиденциальн",
            # Английские
            "legal", "law", "court", "lawyer", "attorney", "contract",
            "regulation", "legaltech", "business", "corporate", "governance",
            "compliance", "risk", "data protection", "privacy", "copyright"
        ]

        # Проверяем наличие хотя бы одного AI keyword
        has_ai = any(keyword in text for keyword in ai_keywords)

        # Проверяем наличие хотя бы одного legal/business keyword
        has_legal_or_business = any(keyword in text for keyword in legal_business_keywords)

        # Релевантна если есть AI ИЛИ legal/business (расширенный фильтр)
        # Более строгая фильтрация будет на этапе AI-анализа
        is_relevant = has_ai or has_legal_or_business

        if not is_relevant:
            logger.debug(
                "article_filtered_irrelevant",
                title=title[:100],
                has_ai=has_ai,
                has_legal_or_business=has_legal_or_business
            )

        return is_relevant

    async def fetch_rss_feed(self, source: Source) -> List[Dict[str, Any]]:
        """
        Получить новости из RSS источника с фильтрацией по AI + legal/business.

        Args:
            source: Объект источника из БД

        Returns:
            Список словарей с новостями
        """
        articles = []
        filtered_count = 0

        logger.info("fetching_rss", source_name=source.name, url=source.url)

        content = await self._fetch_with_retry(source.url)
        if not content:
            return articles

        feed = feedparser.parse(content)

        # Получаем лимит статей из настроек
        max_articles = await get_setting("fetcher.max_articles_per_source", self.db, 300)

        for entry in feed.entries[:max_articles]:
            try:
                article_data = {
                    "url": entry.link,
                    "title": entry.title,
                    "content": entry.get("summary", ""),
                    "source_name": source.name,
                    "published_at": self._parse_date(entry.get("published")),
                }

                # ОТКЛЮЧЕНО: Многие сайты используют consent страницы
                # Используем только краткое содержание из RSS
                # full_content = await self._fetch_article_content(entry.link)
                # if full_content:
                #     article_data["content"] = full_content

                # 🔍 ФИЛЬТРАЦИЯ: Проверяем релевантность по AI + legal/business
                if not self._is_relevant_article(article_data["title"], article_data["content"]):
                    filtered_count += 1
                    logger.info(
                        "article_filtered",
                        source=source.name,
                        title=article_data["title"][:80],
                        reason="not_ai_legal_business"
                    )
                    continue

                articles.append(article_data)

            except Exception as e:
                logger.error(
                    "rss_parse_error",
                    source=source.name,
                    error=str(e)
                )
                continue

        # Вычисляем количество обработанных записей для логирования
        total_processed = min(len(feed.entries), max_articles)

        logger.info(
            "rss_fetch_complete",
            source_name=source.name,
            total_entries=total_processed,
            filtered_out=filtered_count,
            articles_accepted=len(articles)
        )

        return articles

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Парсить дату из различных форматов.

        Args:
            date_str: Строка с датой

        Returns:
            datetime объект или None (без timezone)
        """
        if not date_str:
            return None

        try:
            # feedparser обычно предоставляет parsed время
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            # Убираем timezone для совместимости с БД
            return dt.replace(tzinfo=None) if dt else None
        except Exception:
            try:
                # Fallback на ISO формат
                from dateutil import parser
                dt = parser.parse(date_str)
                # Убираем timezone для совместимости с БД
                return dt.replace(tzinfo=None) if dt else None
            except Exception:
                logger.warning("date_parse_error", date_str=date_str)
                return None

    async def fetch_perplexity_news(self, lang: str = "ru") -> List[Dict[str, Any]]:
        """
        Получить новости через Perplexity AI real-time search.

        Args:
            lang: Язык новостей (ru или en)

        Returns:
            Список словарей с новостями
        """
        articles = []

        # Определяем запрос в зависимости от языка
        if lang == "ru":
            query = settings.google_news_query_ru.replace(" AND ", " ")
            search_prompt = f"""Найди последние новости (за последние 24 часа) по запросу: {query}

Верни результаты в формате JSON массива, где каждый элемент содержит:
- title: заголовок новости
- content: краткое содержание (2-3 предложения)
- url: ссылка на источник
- source_name: название источника
- published_at: дата публикации в формате ISO 8601

Ищи только актуальные новости. Верни максимум 10 новостей."""
        else:
            query = settings.google_news_query_en.replace(" AND ", " ")
            search_prompt = f"""Find latest news (from last 24 hours) for query: {query}

Return results as JSON array where each element contains:
- title: news headline
- content: brief summary (2-3 sentences)
- url: source link
- source_name: source name
- published_at: publication date in ISO 8601 format

Search only for recent news. Return maximum 10 articles."""

        logger.info("fetching_perplexity_news", lang=lang)

        try:
            # Используем LLM provider для Perplexity
            from app.modules.llm_provider import get_llm_provider

            llm = get_llm_provider("perplexity")

            # Делаем запрос к Perplexity с real-time search
            response = await llm.generate_completion(
                messages=[
                    {"role": "system", "content": "You are a news aggregator assistant. Always return valid JSON."},
                    {"role": "user", "content": search_prompt}
                ],
                max_tokens=3000,
                temperature=0.3,
                operation="news_fetch",
                db=self.db
            )

            # Парсим JSON ответ
            import json
            import re

            # Извлекаем JSON из ответа (может быть обернут в markdown)
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Пытаемся парсить весь ответ как JSON
                json_str = response.strip()

            try:
                news_data = json.loads(json_str)

                # Проверяем что это список
                if not isinstance(news_data, list):
                    logger.warning("perplexity_response_not_list", response=response[:200])
                    return articles

                for item in news_data:
                    try:
                        # Парсим дату если есть
                        published_at = None
                        if "published_at" in item and item["published_at"]:
                            published_at = self._parse_date(item["published_at"])

                        # Создаем статью
                        article_data = {
                            "url": item.get("url", ""),
                            "title": item.get("title", ""),
                            "content": item.get("content", ""),
                            "source_name": f"Perplexity Search ({lang.upper()})",
                            "published_at": published_at or datetime.utcnow(),
                        }

                        # Проверяем обязательные поля
                        if article_data["url"] and article_data["title"]:
                            articles.append(article_data)

                            logger.info(
                                "perplexity_article_fetched",
                                lang=lang,
                                title=article_data["title"][:50]
                            )

                    except Exception as e:
                        logger.error(
                            "perplexity_article_parse_error",
                            error=str(e),
                            item=str(item)[:200]
                        )
                        continue

            except json.JSONDecodeError as e:
                logger.error(
                    "perplexity_json_parse_error",
                    error=str(e),
                    response=response[:500]
                )

        except Exception as e:
            logger.error(
                "perplexity_fetch_error",
                lang=lang,
                error=str(e)
            )

        logger.info(
            "perplexity_fetch_complete",
            lang=lang,
            articles_count=len(articles)
        )

        return articles

    async def save_articles(self, articles: List[Dict[str, Any]]) -> int:
        """
        Сохранить статьи в базу данных.

        Args:
            articles: Список статей для сохранения

        Returns:
            Количество сохраненных статей
        """
        saved_count = 0

        for article_data in articles:
            try:
                # ПРЕДВАРИТЕЛЬНАЯ ФИЛЬТРАЦИЯ: проверяем релевантность статьи
                title = article_data.get("title", "")
                content = article_data.get("content", "")

                if not is_article_relevant(title, content):
                    logger.debug("article_filtered_out", title=title[:50])
                    continue

                # 🛡️ ВАЛИДАЦИЯ КОНТЕНТА: защита от мусора
                if not is_content_valid(content, title):
                    logger.info(
                        "article_rejected_invalid_content",
                        title=title[:80],
                        content_length=len(content) if content else 0
                    )
                    continue

                # Проверяем, существует ли статья с таким URL ИЛИ таким заголовком
                result = await self.db.execute(
                    select(RawArticle).where(
                        (RawArticle.url == article_data["url"]) |
                        (RawArticle.title == article_data["title"])
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    logger.debug(
                        "article_exists",
                        url=article_data["url"],
                        title=article_data["title"][:50]
                    )
                    continue

                # Создаем новую статью
                article = RawArticle(**article_data)
                self.db.add(article)
                saved_count += 1

                logger.info(
                    "article_saved",
                    url=article_data["url"],
                    title=article_data["title"][:50]
                )

            except Exception as e:
                logger.error(
                    "article_save_error",
                    error=str(e),
                    url=article_data.get("url", "Unknown")
                )
                continue

        await self.db.commit()

        logger.info("articles_save_complete", saved_count=saved_count)

        return saved_count

    async def fetch_all_sources(self) -> Dict[str, int]:
        """
        Получить новости из всех активных источников.

        Returns:
            Словарь с количеством статей по источникам
        """
        from app.modules.settings_manager import is_source_enabled

        stats = {}

        # Google News RSS (русский) - ЛИМИТ: 10 статей (оптимизировано для экономии)
        if settings.fetcher_enabled and await is_source_enabled("google_news_ru", self.db):
            logger.info("fetching_source", source="google_news_ru", enabled=True)
            articles_ru = await self.fetch_google_news_rss("ru")
            # ОГРАНИЧИВАЕМ количество статей до 10
            articles_ru_limited = articles_ru[:10] if len(articles_ru) > 10 else articles_ru
            saved_ru = await self.save_articles(articles_ru_limited)
            stats["Google News RU"] = saved_ru
        else:
            logger.info("source_disabled", source="google_news_ru")

        # Google News RSS (английский) - ЛИМИТ: 10 статей (оптимизировано для экономии)
        if settings.fetcher_enabled and await is_source_enabled("google_news_en", self.db):
            logger.info("fetching_source", source="google_news_en", enabled=True)
            articles_en = await self.fetch_google_news_rss("en")
            # ОГРАНИЧИВАЕМ количество статей до 10
            articles_en_limited = articles_en[:10] if len(articles_en) > 10 else articles_en
            saved_en = await self.save_articles(articles_en_limited)
            stats["Google News EN"] = saved_en
        else:
            logger.info("source_disabled", source="google_news_en")

        # Perplexity Real-Time Search (русский) - ЛИМИТ: 5 статей (оптимизировано для экономии)
        if settings.perplexity_search_enabled and await is_source_enabled("perplexity_ru", self.db):
            logger.info("fetching_source", source="perplexity_ru", enabled=True)
            perplexity_articles_ru = await self.fetch_perplexity_news("ru")
            # ОГРАНИЧИВАЕМ количество статей до 5
            perplexity_articles_ru_limited = perplexity_articles_ru[:5] if len(perplexity_articles_ru) > 5 else perplexity_articles_ru
            saved_perplexity_ru = await self.save_articles(perplexity_articles_ru_limited)
            stats["Perplexity Search RU"] = saved_perplexity_ru
        else:
            logger.info("source_disabled", source="perplexity_ru")

        # Perplexity Real-Time Search (английский) - ЛИМИТ: 5 статей (оптимизировано для экономии)
        if settings.perplexity_search_enabled and await is_source_enabled("perplexity_en", self.db):
            logger.info("fetching_source", source="perplexity_en", enabled=True)
            perplexity_articles_en = await self.fetch_perplexity_news("en")
            # ОГРАНИЧИВАЕМ количество статей до 5
            perplexity_articles_en_limited = perplexity_articles_en[:5] if len(perplexity_articles_en) > 5 else perplexity_articles_en
            saved_perplexity_en = await self.save_articles(perplexity_articles_en_limited)
            stats["Perplexity Search EN"] = saved_perplexity_en
        else:
            logger.info("source_disabled", source="perplexity_en")

        # 🆕 Telegram Channels (если включен) - ЛИМИТ: 10 статей (оптимизировано для экономии)
        if (settings.telegram_fetch_enabled and
            settings.telegram_api_id and
            settings.telegram_api_hash and
            await is_source_enabled("telegram_channels", self.db)):
            logger.info("fetching_source", source="telegram_channels", enabled=True)

            from app.modules.telegram_fetcher import fetch_telegram_news

            telegram_stats, telegram_articles = await fetch_telegram_news()
            # ОГРАНИЧИВАЕМ количество статей до 10 с Telegram каналов
            telegram_articles_limited = telegram_articles[:10] if len(telegram_articles) > 10 else telegram_articles
            saved_telegram = await self.save_articles(telegram_articles_limited)

            # Добавляем статистику по каждому каналу
            for channel_name, count in telegram_stats.items():
                # count - это сколько было собрано ДО сохранения
                # Но нам нужно знать сколько реально сохранилось
                # Поэтому просто используем общий счетчик
                pass

            # Общая статистика по Telegram
            stats["Telegram Channels"] = saved_telegram

            # Детальная статистика по каналам (для логов)
            logger.info(
                "telegram_detailed_stats",
                channels_stats=telegram_stats,
                total_saved=saved_telegram
            )
        else:
            logger.info("source_disabled", source="telegram_channels")

        # Дополнительные RSS источники из БД
        result = await self.db.execute(
            select(Source).where(Source.enabled == True, Source.type == "rss")
        )
        sources = result.scalars().all()

        for source in sources:
            try:
                articles = await self.fetch_rss_feed(source)
                # ОГРАНИЧИВАЕМ количество статей до 10 с RSS источников (оптимизировано для экономии)
                articles_limited = articles[:10] if len(articles) > 10 else articles
                saved = await self.save_articles(articles_limited)
                stats[source.name] = saved

                # Обновляем статистику источника
                source.last_fetch = datetime.utcnow()
                source.fetch_errors = 0

            except Exception as e:
                logger.error(
                    "source_fetch_failed",
                    source_name=source.name,
                    error=str(e)
                )
                source.fetch_errors += 1

        await self.db.commit()

        # Логируем общую статистику
        total_articles = sum(stats.values())
        await log_to_db(
            "INFO",
            f"Fetch completed: {total_articles} articles from {len(stats)} sources",
            {"stats": stats},
            session=self.db  # Передаём существующую сессию
        )

        logger.info(
            "fetch_all_complete",
            total_articles=total_articles,
            sources_count=len(stats),
            stats=stats
        )

        return stats


async def fetch_news(db_session: AsyncSession) -> Dict[str, int]:
    """
    Удобная функция для запуска сбора новостей.

    Args:
        db_session: Асинхронная сессия БД

    Returns:
        Статистика по собранным новостям
    """
    async with NewsFetcher(db_session) as fetcher:
        return await fetcher.fetch_all_sources()
