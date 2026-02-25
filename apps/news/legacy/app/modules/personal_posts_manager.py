"""
Personal Posts Manager - управление личными постами пользователя.
Дневник работы с AI, векторизация, поиск связей с публикациями.
"""

import asyncio
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

import openai
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import PersonalPost, RawArticle
import structlog

logger = structlog.get_logger()


# ====================
# Core Functions
# ====================

async def create_personal_post(
    user_id: int,
    content: str,
    db: AsyncSession,
    title: Optional[str] = None,
    creation_method: str = "manual",
    raw_input: Optional[str] = None,
    ai_model_used: Optional[str] = None
) -> PersonalPost:
    """
    Создать личный пост.

    Args:
        user_id: Telegram user ID
        content: Текст поста
        db: Database session
        title: Заголовок (опционально)
        creation_method: manual, ai_assisted, voice
        raw_input: Оригинальный ввод до обработки
        ai_model_used: Модель AI если использовалась

    Returns:
        Созданный PersonalPost объект
    """
    # Создаём пост
    post = PersonalPost(
        user_id=user_id,
        title=title,
        content=content,
        raw_input=raw_input or content,
        creation_method=creation_method,
        ai_model_used=ai_model_used,
        iterations_count=1
    )

    db.add(post)
    await db.flush()  # Получаем ID

    logger.info(
        "personal_post_created",
        user_id=user_id,
        post_id=post.id,
        method=creation_method,
        content_length=len(content)
    )

    return post


async def generate_post_with_ai(
    user_input: str,
    model: str = "gpt-4o",
    previous_attempts: Optional[List[str]] = None
) -> str:
    """
    Сгенерировать пост с помощью AI.

    Args:
        user_input: Идеи пользователя
        model: Модель OpenAI
        previous_attempts: Предыдущие попытки для контекста

    Returns:
        Сгенерированный текст поста
    """
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    # Формируем промпт
    system_prompt = """Ты - помощник для создания постов в личном дневнике о работе с AI.

Твоя задача:
- Помочь пользователю сформулировать его мысли и идеи
- Создать структурированный, интересный пост
- Сохранить личный стиль и голос пользователя
- Добавить детали и контекст там где нужно
- Сделать пост читабельным и вовлекающим

Формат поста:
- Заголовок (если нужен)
- Основной текст с параграфами
- Можно использовать эмодзи для акцентов
- Длина: 300-800 слов
- Стиль: личный, искренний, информативный

НЕ надо:
- Писать слишком формально
- Добавлять рекламные призывы
- Использовать шаблонные фразы
- Делать слишком длинно или слишком коротко"""

    messages = [
        {"role": "system", "content": system_prompt},
    ]

    # Добавляем предыдущие попытки для контекста
    if previous_attempts:
        messages.append({
            "role": "user",
            "content": f"Вот мои предыдущие попытки, которые мне не понравились:\n\n" +
                      "\n\n---\n\n".join(previous_attempts) +
                      "\n\nПожалуйста, создай новую версию с учётом этого."
        })

    # Добавляем текущий ввод
    messages.append({
        "role": "user",
        "content": f"Идеи для поста:\n\n{user_input}\n\nСоздай пост на основе этих идей."
    })

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.8,  # Больше креативности
            max_tokens=2000
        )

        generated_text = response.choices[0].message.content

        logger.info(
            "ai_post_generated",
            model=model,
            input_length=len(user_input),
            output_length=len(generated_text)
        )

        return generated_text

    except Exception as e:
        logger.error("ai_generation_error", error=str(e))
        raise


async def analyze_post_with_ai(
    content: str,
    model: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """
    Анализировать пост с помощью AI для категоризации и извлечения тегов.

    Args:
        content: Текст поста
        model: Модель OpenAI

    Returns:
        Dict с category, tags, sentiment
    """
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    prompt = f"""Проанализируй этот личный пост о работе с AI и верни JSON со следующими полями:

1. category: основная тема поста (одна из: ai_tools, ai_insights, experiments, challenges, success_story, learning, thoughts, other)
2. tags: список тегов (3-7 тегов) для поиска и категоризации
3. sentiment: общий тон поста (positive, neutral, negative)

Пост:
{content}

Верни ТОЛЬКО валидный JSON без дополнительных объяснений."""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Ты - аналитик контента. Отвечай только в формате JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )

        import json
        analysis = json.loads(response.choices[0].message.content)

        logger.info(
            "post_analyzed",
            category=analysis.get("category"),
            tags_count=len(analysis.get("tags", [])),
            sentiment=analysis.get("sentiment")
        )

        return analysis

    except Exception as e:
        logger.error("ai_analysis_error", error=str(e))
        # Fallback значения
        return {
            "category": "other",
            "tags": ["ai", "personal"],
            "sentiment": "neutral"
        }


async def vectorize_post(
    content: str,
    model: str = "text-embedding-3-small"
) -> List[float]:
    """
    Векторизовать текст поста для RAG.

    Args:
        content: Текст поста
        model: Модель embeddings

    Returns:
        Embedding vector (1536 dimensions)
    """
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        response = await client.embeddings.create(
            model=model,
            input=content,
            encoding_format="float"
        )

        embedding = response.data[0].embedding

        logger.info(
            "post_vectorized",
            model=model,
            dimension=len(embedding),
            content_length=len(content)
        )

        return embedding

    except Exception as e:
        logger.error("vectorization_error", error=str(e))
        raise


async def find_similar_articles(
    post_embedding: List[float],
    db: AsyncSession,
    limit: int = 5,
    min_similarity: float = 0.7
) -> List[Tuple[int, float]]:
    """
    Найти похожие статьи по векторному представлению.

    Args:
        post_embedding: Embedding вектор поста
        db: Database session
        limit: Количество результатов
        min_similarity: Минимальная схожесть (0.0-1.0)

    Returns:
        List of (article_id, similarity_score)
    """
    # TODO: Реализовать когда будет pgvector или Qdrant
    # Пока возвращаем пустой список
    logger.info(
        "similarity_search_skipped",
        reason="pgvector_not_configured",
        embedding_dim=len(post_embedding)
    )
    return []


async def enrich_post_with_metadata(
    post: PersonalPost,
    db: AsyncSession
) -> None:
    """
    Обогатить пост метаданными: категория, теги, sentiment, векторы, связи.

    Args:
        post: PersonalPost объект
        db: Database session
    """
    # 1. AI анализ для категорий и тегов
    analysis = await analyze_post_with_ai(post.content)
    post.category = analysis.get("category")
    post.tags = analysis.get("tags", [])
    post.sentiment = analysis.get("sentiment")

    # 2. Векторизация
    try:
        embedding = await vectorize_post(post.content)
        post.embedding_vector = embedding
        post.embedding_model = "text-embedding-3-small"

        # 3. Поиск похожих статей
        similar = await find_similar_articles(embedding, db)
        if similar:
            post.related_article_ids = [article_id for article_id, _ in similar]
            post.similarity_scores = [score for _, score in similar]

    except Exception as e:
        logger.error(
            "post_enrichment_error",
            post_id=post.id,
            error=str(e)
        )

    await db.commit()

    logger.info(
        "post_enriched",
        post_id=post.id,
        category=post.category,
        tags_count=len(post.tags or []),
        similar_articles=len(post.related_article_ids or [])
    )


async def get_user_posts(
    user_id: int,
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0
) -> List[PersonalPost]:
    """
    Получить личные посты пользователя.

    Args:
        user_id: Telegram user ID
        db: Database session
        limit: Количество постов
        offset: Смещение для пагинации

    Returns:
        Список постов
    """
    result = await db.execute(
        select(PersonalPost)
        .where(PersonalPost.user_id == user_id)
        .order_by(desc(PersonalPost.created_at))
        .limit(limit)
        .offset(offset)
    )

    posts = result.scalars().all()
    return list(posts)


async def delete_post(post_id: int, user_id: int, db: AsyncSession) -> bool:
    """
    Удалить личный пост.

    Args:
        post_id: ID поста
        user_id: Telegram user ID (для проверки прав)
        db: Database session

    Returns:
        True если удалён, False если не найден
    """
    result = await db.execute(
        select(PersonalPost)
        .where(
            PersonalPost.id == post_id,
            PersonalPost.user_id == user_id
        )
    )
    post = result.scalar_one_or_none()

    if not post:
        return False

    await db.delete(post)
    await db.commit()

    logger.info("personal_post_deleted", post_id=post_id, user_id=user_id)
    return True


# УДАЛЕНО: transcribe_voice() - теперь используем встроенное распознавание Telegram
# Функция больше не нужна, так как Telegram предоставляет бесплатное распознавание
# через message.voice.transcription для Premium пользователей
