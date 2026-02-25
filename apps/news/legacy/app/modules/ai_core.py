"""
AI Core Module
Интеллектуальный анализ новостей и генерация драфтов с использованием LLM API.

Функционал:
1. Ранжирование новостей по важности (OpenAI/Perplexity)
2. Контекстная проверка (упрощенный RAG с PostgreSQL Full-Text Search)
3. Генерация драфтов постов для Telegram
"""

import asyncio
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import RawArticle, PostDraft, LegalKnowledge, log_to_db
from app.modules.llm_provider import get_llm_provider
from app.modules.vector_search import get_vector_search
import structlog

logger = structlog.get_logger()


# ОПТИМИЗИРОВАННЫЕ ПРОМПТЫ для снижения расходов
RANKING_SYSTEM_PROMPT = """Оцени ценность новости для бизнеса и LegalTech (0-10):

Критерии:
- Бизнес-ценность AI (40%)
- Юридические/комплаенс аспекты (30%)
- Российский рынок (20%)
- Новизна (10%)

ПРИОРИТЕТЫ: +2 балла за российские новости/компании, +2 балла за разработку AI.

Отвечай ТОЛЬКО числом от 0 до 10."""

DRAFT_SYSTEM_PROMPT = """Создай пост для канала об AI в бизнесе.

ИСПОЛЬЗУЙ ТОЛЬКО ФАКТЫ ИЗ СТАТЬИ: конкретные цифры, имена компаний, даты, цитаты.

Структура поста:
```
[🌍 Международные новости: если не Россия]

[Эмодзи] КОНКРЕТНЫЙ ЗАГОЛОВОК (60-80 символов)

📊 ЧТО ПРОИСХОДИТ:
Подробности события с точными фактами из статьи

💼 БИЗНЕС-ЦЕННОСТЬ:
Конкретные преимущества и ROI с цифрами

⚖️ ЮРИДИЧЕСКИЕ АСПЕКТЫ:
Legal/compliance детали из статьи

🎯 ВЫВОДЫ:
Практические рекомендации

#ИИвБизнесе #AI #LegalTech
```

ДЛИНА: 1200-1500 символов. НЕ выдумывай факты!"""


class AICore:
    """Ядро AI анализа и генерации контента."""

    def __init__(self, db_session: AsyncSession, provider: str = None):
        """
        Инициализация AI Core.

        Args:
            db_session: Асинхронная сессия базы данных
            provider: LLM провайдер ('openai' или 'perplexity'). Если None, используется default из settings.
        """
        self.db = db_session
        self.provider = provider or settings.default_llm_provider
        self.llm = get_llm_provider(self.provider)

    async def rank_articles(
        self,
        articles: List[RawArticle],
        top_n: Optional[int] = None
    ) -> List[Tuple[RawArticle, float]]:
        """
        Ранжировать статьи по важности с использованием GPT.

        Args:
            articles: Список статей для ранжирования
            top_n: Количество топ статей (по умолчанию из настроек)

        Returns:
            Список пар (статья, оценка) отсортированных по убыванию оценки
        """
        if top_n is None:
            top_n = settings.ai_top_articles_count

        if not articles:
            logger.warning("no_articles_to_rank")
            return []

        logger.info("ranking_articles", count=len(articles))

        # Получаем статистику источников за последние 7 дней для diversity boost
        from datetime import timedelta
        date_from = datetime.utcnow() - timedelta(days=7)

        query_sources = text("""
            SELECT ra.source_name, COUNT(*) as pub_count
            FROM publications p
            JOIN post_drafts pd ON p.draft_id = pd.id
            JOIN raw_articles ra ON pd.article_id = ra.id
            WHERE p.published_at >= :date_from
            GROUP BY ra.source_name
        """)
        result_sources = await self.db.execute(query_sources, {"date_from": date_from})
        source_counts = {row.source_name: row.pub_count for row in result_sources}

        max_source_count = max(source_counts.values()) if source_counts else 0

        logger.info(
            "source_diversity_stats",
            sources=source_counts,
            max_count=max_source_count
        )

        ranked_articles = []

        # Ранжируем каждую статью
        for article in articles:
            try:
                # ПРОВЕРКА КЭША: если статья уже оценивалась менее 24 часов назад, используем кэшированную оценку
                from datetime import timedelta
                cache_age = timedelta(hours=24)

                if (article.relevance_score is not None and
                    article.scored_at and
                    datetime.utcnow() - article.scored_at < cache_age):

                    logger.debug(
                        "using_cached_score",
                        article_id=article.id,
                        cached_score=article.relevance_score,
                        scored_at=article.scored_at
                    )
                    # Обновляем статус на 'processed' для кэшированных статей
                    article.status = 'processed'
                    ranked_articles.append((article, article.relevance_score))
                    continue
                # Формируем промпт для оценки
                user_prompt = f"""Новость:
Заголовок: {article.title}

Содержание:
{article.content[:1000] if article.content else article.title}

Источник: {article.source_name}

Оцени ценность этой новости для целевой аудитории (бизнес-руководители + юристы, думающие о внедрении AI) от 0 до 10."""

                # Запрос к LLM (оптимизировано для экономии)
                response = await self._call_llm(
                    system_prompt=RANKING_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    max_tokens=5,  # Уменьшено с 10 до 5 для экономии
                    operation="ranking",
                    temperature=0.1  # Минимальная температура для консистентности
                )

                # Парсим оценку
                try:
                    base_score = float(response.strip())
                    base_score = max(0.0, min(10.0, base_score))  # Ограничиваем 0-10
                except ValueError:
                    logger.warning(
                        "invalid_score",
                        article_id=article.id,
                        response=response
                    )
                    base_score = 5.0  # Средняя оценка по умолчанию

                # Применяем diversity boost
                # Источники, которые публиковались меньше, получают boost
                source_pub_count = source_counts.get(article.source_name, 0)

                # Diversity boost: чем меньше публикаций из источника, тем больше boost
                # Источники с 0 публикаций: +1.5 балла
                # Источники с публикациями ниже среднего: +0.5-1.0 балла
                # Источники с публикациями выше среднего: -0.5 балла
                if max_source_count > 0:
                    avg_count = sum(source_counts.values()) / len(source_counts) if source_counts else 0

                    if source_pub_count == 0:
                        diversity_boost = 1.5
                    elif source_pub_count < avg_count:
                        diversity_boost = 1.0
                    elif source_pub_count > max_source_count * 0.7:
                        diversity_boost = -0.5
                    else:
                        diversity_boost = 0.0
                else:
                    # Нет статистики - нет boost
                    diversity_boost = 0.0

                final_score = max(0.0, min(10.0, base_score + diversity_boost))

                # СОХРАНЯЕМ оценку и время оценки в кэш
                article.relevance_score = final_score
                article.scored_at = datetime.utcnow()

                ranked_articles.append((article, final_score))

                logger.info(
                    "article_ranked",
                    article_id=article.id,
                    title=article.title[:50],
                    source=article.source_name,
                    base_score=base_score,
                    diversity_boost=diversity_boost,
                    final_score=final_score,
                    source_pub_count=source_pub_count
                )

                # Rate limiting
                await asyncio.sleep(1)  # 60 requests per minute

            except Exception as e:
                logger.error(
                    "ranking_error",
                    article_id=article.id,
                    error=str(e)
                )
                # Добавляем с минимальной оценкой при ошибке
                ranked_articles.append((article, 0.0))

        # Сортируем по убыванию оценки
        ranked_articles.sort(key=lambda x: x[1], reverse=True)

        # Возвращаем топ-N
        top_articles = ranked_articles[:top_n]

        logger.info(
            "ranking_complete",
            total=len(articles),
            top_n=len(top_articles),
            top_scores=[score for _, score in top_articles]
        )

        return top_articles

    async def search_legal_context(
        self,
        query: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Поиск релевантного юридического контекста в базе знаний.

        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов

        Returns:
            Список найденных фрагментов документов
        """
        if not settings.ai_legal_context_enabled:
            return []

        try:
            # PostgreSQL Full-Text Search
            sql = text("""
                SELECT
                    id,
                    doc_name,
                    article_number,
                    text_chunk,
                    ts_rank(ts_vector, plainto_tsquery('russian', :query)) as rank
                FROM legal_knowledge
                WHERE ts_vector @@ plainto_tsquery('russian', :query)
                ORDER BY rank DESC
                LIMIT :limit
            """)

            result = await self.db.execute(
                sql,
                {"query": query, "limit": limit}
            )

            contexts = []
            for row in result:
                contexts.append({
                    "doc_name": row.doc_name,
                    "article_number": row.article_number,
                    "text": row.text_chunk,
                    "relevance": float(row.rank)
                })

            logger.info(
                "legal_context_search",
                query=query[:50],
                results_count=len(contexts)
            )

            return contexts

        except Exception as e:
            logger.error(
                "legal_context_search_error",
                query=query[:50],
                error=str(e)
            )
            return []

    async def generate_draft(
        self,
        article: RawArticle,
        score: float
    ) -> Optional[PostDraft]:
        """
        Сгенерировать драфт поста из статьи.

        Args:
            article: Статья для обработки
            score: Оценка важности статьи

        Returns:
            PostDraft или None при ошибке
        """
        try:
            logger.info(
                "generating_draft",
                article_id=article.id,
                title=article.title[:50]
            )

            # 1. Поиск юридического контекста
            legal_context_text = None
            confidence_score = score / 10.0  # Нормализуем к 0-1

            if settings.ai_legal_context_enabled:
                # Формируем поисковый запрос из заголовка и ключевых слов
                search_query = f"{article.title} {article.content[:200] if article.content else ''}"

                contexts = await self.search_legal_context(search_query)

                if contexts and contexts[0]["relevance"] >= settings.ai_legal_context_confidence_min:
                    # Берем топ контекст
                    top_context = contexts[0]
                    legal_context_text = f"{top_context['doc_name']}"
                    if top_context['article_number']:
                        legal_context_text += f", статья {top_context['article_number']}"
                    legal_context_text += f": {top_context['text'][:200]}..."

                    logger.info(
                        "legal_context_found",
                        article_id=article.id,
                        doc=top_context['doc_name'],
                        relevance=top_context['relevance']
                    )

            # 2. Получаем RAG контекст (похожие посты + примеры)
            rag_similar = []
            rag_positive = []
            rag_negative = []

            if settings.qdrant_enabled:
                try:
                    vector_search = get_vector_search()

                    # Получаем RAG контекст на основе content статьи
                    draft_preview = f"{article.title}\n\n{article.content[:500] if article.content else ''}"
                    rag_similar, rag_positive, rag_negative = await vector_search.get_rag_context(draft_preview)

                    logger.info(
                        "rag_context_obtained",
                        article_id=article.id,
                        similar_count=len(rag_similar),
                        positive_count=len(rag_positive),
                        negative_count=len(rag_negative)
                    )
                except Exception as e:
                    logger.warning("rag_context_error", error=str(e), article_id=article.id)
                    # Продолжаем без RAG если ошибка

            # 3. Формируем промпт для генерации поста
            user_prompt = f"""Новость для переписывания:

Заголовок: {article.title}

Содержание:
{article.content if article.content else article.title}

Источник: {article.source_name}"""

            if legal_context_text:
                user_prompt += f"""

Найден юридический контекст:
{legal_context_text}

Включи краткую ссылку на него в раздел "ДЛЯ ЮРИСТА" если релевантно."""

            # Добавляем RAG контекст для избежания банальности и повторений
            if rag_negative:
                user_prompt += "\n\n🚫 НЕГАТИВНЫЕ ПРИМЕРЫ (НЕ ПИШ�� ТАК - это посты с плохими реакциями):\n"
                for i, neg in enumerate(rag_negative[:3], 1):
                    reactions_str = ', '.join([f"{k}: {v}" for k, v in neg.get('reactions', {}).items()])
                    user_prompt += f"\n{i}. {neg['content'][:150]}...\n   Реакции: {reactions_str}\n"

            if rag_positive:
                user_prompt += "\n\n✅ ПОЗИТИВНЫЕ ПРИМЕРЫ (ПИШИ ТАК - это посты с хорошими реакциями):\n"
                for i, pos in enumerate(rag_positive[:3], 1):
                    reactions_str = ', '.join([f"{k}: {v}" for k, v in pos.get('reactions', {}).items()])
                    user_prompt += f"\n{i}. {pos['content'][:150]}...\n   Реакции: {reactions_str}\n"

            if rag_similar:
                user_prompt += "\n\n⚠️ ПОХОЖИЕ УЖЕ ОПУБЛИКОВАННЫЕ ПОСТЫ (НЕ ПОВТОРЯЙ ЭТИ ИДЕИ):\n"
                for i, sim in enumerate(rag_similar[:5], 1):
                    user_prompt += f"\n{i}. (Похожесть: {sim['score']:.0%}) {sim['content'][:150]}...\n"

            user_prompt += "\n\nСоздай пост для Telegram канала согласно инструкциям. УЧИТЫВАЙ примеры и НЕ ПОВТОРЯЙ похожие посты!"

            # 4. Генерируем пост через LLM
            draft_content = await self._call_llm(
                system_prompt=DRAFT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=settings.openai_max_tokens,
                operation="draft_generation",
                temperature=settings.openai_temperature
            )

            # 4. Извлекаем заголовок из сгенерированного контента
            lines = draft_content.split('\n')

            # Пропускаем маркеры международных новостей и пустые строки
            intl_markers = ["🌍 Международные новости:", "🌎 За рубежом:", "🌏 В мире:",
                           "🌐 Новости из-за рубежа:", "🗺️ Зарубежный опыт:"]

            title = article.title  # Заголовок по умолчанию
            for line in lines:
                line_stripped = line.strip()
                # Пропускаем пустые строки и маркеры международных новостей
                if line_stripped and line_stripped not in intl_markers:
                    title = line_stripped
                    break

            # Убираем эмодзи и HTML теги из заголовка для хранения
            import re
            title_clean = re.sub(r'<[^>]+>', '', title)  # Убираем HTML теги
            title_clean = ''.join(c for c in title_clean if c.isalnum() or c.isspace() or c in '.,!?-:;')
            title_clean = title_clean.strip()

            # 5. Создаем драфт
            draft = PostDraft(
                article_id=article.id,
                title=title_clean[:200],  # Ограничиваем длину
                content=draft_content,
                legal_context=legal_context_text,
                confidence_score=confidence_score,
                status='pending_review'
            )

            self.db.add(draft)

            # 6. Обновляем статус статьи
            article.status = 'processed'

            await self.db.commit()
            await self.db.refresh(draft)

            logger.info(
                "draft_generated",
                draft_id=draft.id,
                article_id=article.id,
                confidence=confidence_score
            )

            return draft

        except Exception as e:
            logger.error(
                "draft_generation_error",
                article_id=article.id,
                error=str(e)
            )
            return None

    async def process_filtered_articles(self) -> Dict[str, Any]:
        """
        Обработать все отфильтрованные статьи.

        Returns:
            Статистика обработки
        """
        stats = {
            "total": 0,
            "ranked": 0,
            "drafts_created": 0,
            "errors": 0
        }

        # Получаем отфильтрованные статьи
        result = await self.db.execute(
            select(RawArticle).where(RawArticle.status == 'filtered')
        )
        articles = list(result.scalars().all())
        stats["total"] = len(articles)

        if not articles:
            logger.info("no_filtered_articles_to_process")
            return stats

        logger.info("processing_filtered_articles", count=len(articles))

        # Ранжируем статьи
        ranked_articles = await self.rank_articles(articles)
        stats["ranked"] = len(ranked_articles)

        # СОХРАНЯЕМ изменения в базу данных (оценки и время оценки)
        await self.db.commit()

        # Генерируем драфты для топ статей
        for article, score in ranked_articles:
            try:
                draft = await self.generate_draft(article, score)
                if draft:
                    stats["drafts_created"] += 1
                else:
                    stats["errors"] += 1

            except Exception as e:
                logger.error(
                    "article_processing_error",
                    article_id=article.id,
                    error=str(e)
                )
                stats["errors"] += 1

        # Логируем статистику
        await log_to_db(
            "INFO",
            f"AI processing completed: {stats['drafts_created']} drafts created",
            stats,
            session=self.db  # Передаём существующую сессию
        )

        logger.info("ai_processing_complete", **stats)

        return stats

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        operation: str = "completion"
    ) -> str:
        """
        Вызвать LLM API с retry механизмом.

        Args:
            system_prompt: Системный промпт
            user_prompt: Пользовательский промпт
            max_tokens: Максимум токенов
            temperature: Температура
            operation: Тип операции (ranking, draft_generation, analysis, etc)

        Returns:
            Ответ модели
        """
        try:
            result = await self.llm.generate_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                operation=operation,
                db=self.db
            )

            return result

        except Exception as e:
            logger.error(
                "llm_api_error",
                provider=self.provider,
                error=str(e)
            )
            raise


async def call_openai_chat(
    messages: List[Dict[str, str]],
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: int = 2000,
    db: Optional[AsyncSession] = None,
    operation: str = "ai_analysis"
) -> Tuple[str, Dict[str, Any]]:
    """
    Прямой вызов OpenAI Chat API для аналитики.

    Args:
        messages: Список сообщений для GPT (формат [{"role": "user", "content": "..."}])
        model: Модель GPT (по умолчанию gpt-4o)
        temperature: Температура генерации (0-2)
        max_tokens: Максимум токенов в ответе
        db: Database session для логирования (опционально)
        operation: Тип операции (для логов)

    Returns:
        Tuple[str, Dict]: (Ответ от GPT-4, статистика использования)
    """
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        result = response.choices[0].message.content

        # Расчет стоимости
        # Pricing определяется по модели:
        # GPT-4o: Input $2.50/1M, Output $10.00/1M
        # GPT-4o-mini: Input $0.150/1M, Output $0.600/1M (в 16 раз дешевле!)
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        # Определяем цены в зависимости от модели
        if "gpt-4o-mini" in model.lower():
            input_price_per_1m = 0.150
            output_price_per_1m = 0.600
        elif "gpt-4o" in model.lower():
            input_price_per_1m = 2.50
            output_price_per_1m = 10.00
        else:
            # Дефолтные цены для других моделей
            input_price_per_1m = 2.50
            output_price_per_1m = 10.00

        cost_usd = (
            (prompt_tokens / 1_000_000 * input_price_per_1m) +
            (completion_tokens / 1_000_000 * output_price_per_1m)
        )

        usage_stats = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost_usd, 6)
        }

        logger.info(
            "openai_chat_call",
            model=model,
            operation=operation,
            **usage_stats
        )

        # Логируем в БД если передана сессия
        if db:
            from app.models.database import APIUsage

            api_log = APIUsage(
                provider="openai",
                model=model,
                operation=operation,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd
            )
            db.add(api_log)
            await db.commit()

        return result, usage_stats

    except Exception as e:
        logger.error("openai_chat_error", error=str(e), model=model)
        raise


async def process_articles_with_ai(db_session: AsyncSession, provider: str = None) -> Dict[str, Any]:
    """
    Удобная функция для запуска AI обработки статей.

    Args:
        db_session: Асинхронная сессия БД
        provider: LLM провайдер ('openai' или 'perplexity'). Если None, используется default из settings.

    Returns:
        Статистика обработки
    """
    ai_core = AICore(db_session, provider=provider)
    return await ai_core.process_filtered_articles()
