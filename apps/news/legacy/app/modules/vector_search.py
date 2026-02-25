"""
Vector Search Module
Модуль векторного поиска для избежания банальности и повторений в постах.

Функционал:
1. Векторизация текста через sentence-transformers
2. Поиск семантически похожих постов
3. Поиск позитивных/негативных примеров по реакциям
4. RAG для генерации с учетом опыта
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import structlog

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range
)
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = structlog.get_logger()


class VectorSearch:
    """Класс для векторного поиска и RAG."""

    # Название коллекции в Qdrant
    COLLECTION_NAME = "legal_ai_publications"

    # Размерность векторов (зависит от модели)
    VECTOR_SIZE = 768  # paraphrase-multilingual-mpnet-base-v2

    def __init__(self):
        """Инициализация векторного поиска."""
        try:
            # Подключаемся к Qdrant
            self.client = QdrantClient(
                host=getattr(settings, "qdrant_host", "qdrant"),
                port=getattr(settings, "qdrant_port", 6333),
                timeout=30
            )

            # Загружаем модель для векторизации (многоязычная, поддерживает русский)
            self.model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')

            # Инициализируем коллекцию если её нет
            self._init_collection()

            logger.info(
                "vector_search_initialized",
                collection=self.COLLECTION_NAME,
                vector_size=self.VECTOR_SIZE
            )

        except Exception as e:
            logger.error("vector_search_init_error", error=str(e))
            raise

    def _init_collection(self):
        """Инициализация коллекции в Qdrant (если не существует)."""
        try:
            # Проверяем существование коллекции
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.COLLECTION_NAME not in collection_names:
                # Создаем коллекцию
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE
                    )
                )
                logger.info("qdrant_collection_created", collection=self.COLLECTION_NAME)
            else:
                logger.info("qdrant_collection_exists", collection=self.COLLECTION_NAME)

        except Exception as e:
            logger.error("qdrant_collection_init_error", error=str(e))
            raise

    def vectorize(self, text: str) -> List[float]:
        """
        Векторизация текста.

        Args:
            text: Текст для векторизации

        Returns:
            Вектор (список float)
        """
        try:
            vector = self.model.encode(text, convert_to_numpy=True)
            return vector.tolist()
        except Exception as e:
            logger.error("vectorization_error", error=str(e), text_len=len(text))
            raise

    async def add_publication(
        self,
        pub_id: int,
        content: str,
        published_at: datetime,
        reactions: Optional[Dict] = None
    ):
        """
        Добавление опубликованного поста в векторную БД.

        Args:
            pub_id: ID публикации
            content: Текст публикации
            published_at: Дата публикации
            reactions: Словарь реакций (useful, important, banal, etc.)
        """
        try:
            # Векторизуем контент в thread pool (не блокирует event loop)
            import asyncio
            loop = asyncio.get_event_loop()
            vector = await loop.run_in_executor(None, self.vectorize, content)

            # Формируем payload с метаданными
            payload = {
                "publication_id": pub_id,
                "content": content[:500],  # Первые 500 символов для preview
                "published_at": published_at.isoformat(),
                "reactions": reactions or {},
                # Подсчитываем балл качества на основе реакций
                "quality_score": self._calculate_quality_score(reactions)
            }

            # Добавляем в Qdrant
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=pub_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )

            logger.info(
                "publication_vectorized",
                pub_id=pub_id,
                quality_score=payload["quality_score"]
            )

        except Exception as e:
            logger.error(
                "add_publication_error",
                pub_id=pub_id,
                error=str(e)
            )
            # Не падаем - векторизация не критична

    def _calculate_quality_score(self, reactions: Optional[Dict]) -> float:
        """
        Расчет балла качества на основе реакций.

        Args:
            reactions: Словарь реакций

        Returns:
            Балл от -1.0 до 1.0
        """
        if not reactions:
            return 0.0

        # Позитивные реакции
        positive = reactions.get("useful", 0) + reactions.get("important", 0)

        # Негативные реакции
        negative = (
            reactions.get("banal", 0) +
            reactions.get("obvious", 0) +
            reactions.get("poor_quality", 0) +
            reactions.get("low_content_quality", 0) +
            reactions.get("bad_source", 0)
        )

        # Нейтральные
        neutral = reactions.get("controversial", 0)

        total = positive + negative + neutral

        if total == 0:
            return 0.0

        # Балл: (+1 за позитивные, -1 за негативные, 0 за нейтральные) / total
        score = (positive - negative) / total
        return max(-1.0, min(1.0, score))

    def update_quality_score(self, pub_id: int, reactions: Dict):
        """
        Обновить quality_score для публикации в векторной БД.

        Args:
            pub_id: ID публикации
            reactions: Новый словарь реакций
        """
        try:
            # Рассчитываем новый quality score
            quality_score = self._calculate_quality_score(reactions)

            # Обновляем payload в Qdrant
            self.client.set_payload(
                collection_name=self.COLLECTION_NAME,
                payload={
                    "reactions": reactions,
                    "quality_score": quality_score
                },
                points=[pub_id]
            )

            logger.info(
                "quality_score_updated",
                pub_id=pub_id,
                quality_score=quality_score,
                total_reactions=sum(reactions.values()) if reactions else 0
            )

        except Exception as e:
            logger.error(
                "update_quality_score_error",
                pub_id=pub_id,
                error=str(e)
            )
            # Не падаем - обновление не критично

    async def find_similar(
        self,
        text: str,
        limit: int = 5,
        score_threshold: float = 0.75
    ) -> List[Dict]:
        """
        Поиск похожих постов.

        Args:
            text: Текст для поиска
            limit: Максимум результатов
            score_threshold: Минимальный порог похожести (0-1)

        Returns:
            Список похожих постов с метаданными
        """
        try:
            # Векторизуем запрос в thread pool (не блокирует event loop)
            import asyncio
            loop = asyncio.get_event_loop()
            query_vector = await loop.run_in_executor(None, self.vectorize, text)

            # Ищем похожие
            results = self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold
            )

            # Форматируем результаты
            similar_posts = []
            for result in results:
                similar_posts.append({
                    "id": result.id,
                    "score": result.score,
                    "content": result.payload.get("content", ""),
                    "published_at": result.payload.get("published_at"),
                    "quality_score": result.payload.get("quality_score", 0.0)
                })

            logger.info(
                "similar_search_completed",
                found=len(similar_posts),
                threshold=score_threshold
            )

            return similar_posts

        except Exception as e:
            logger.error("similar_search_error", error=str(e))
            return []

    async def find_examples_by_quality(
        self,
        positive: bool = True,
        limit: int = 3,
        days_back: int = 30
    ) -> List[Dict]:
        """
        Поиск постов с хорошими/плохими реакциями для обучения.

        Args:
            positive: True = позитивные примеры, False = негативные
            limit: Максимум результатов
            days_back: Искать за последние N дней

        Returns:
            Список постов-примеров
        """
        try:
            # Дата фильтра
            date_from = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

            # Фильтр по quality_score
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="published_at",
                        range=Range(gte=date_from)
                    ),
                    FieldCondition(
                        key="quality_score",
                        range=Range(
                            gte=0.5 if positive else None,
                            lte=-0.3 if not positive else None
                        )
                    )
                ]
            )

            # Scroll через все точки с фильтром
            results, _ = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=filter_condition,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )

            # Форматируем результаты
            examples = []
            for point in results:
                examples.append({
                    "id": point.id,
                    "content": point.payload.get("content", ""),
                    "quality_score": point.payload.get("quality_score", 0.0),
                    "reactions": point.payload.get("reactions", {})
                })

            logger.info(
                "quality_examples_found",
                positive=positive,
                count=len(examples)
            )

            return examples

        except Exception as e:
            logger.error("quality_examples_error", error=str(e), positive=positive)
            return []

    async def get_rag_context(
        self,
        draft_text: str
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Получить полный RAG контекст для генерации.

        Args:
            draft_text: Текст черновика

        Returns:
            Tuple: (похожие_посты, позитивные_примеры, негативные_примеры)
        """
        # Ищем похожие посты (чтобы не повторяться)
        similar = await self.find_similar(draft_text, limit=5, score_threshold=0.75)

        # Ищем позитивные примеры (чтобы писать ТАК)
        positive = await self.find_examples_by_quality(positive=True, limit=3)

        # Ищем негативные примеры (чтобы НЕ писать так)
        negative = await self.find_examples_by_quality(positive=False, limit=3)

        logger.info(
            "rag_context_prepared",
            similar_count=len(similar),
            positive_count=len(positive),
            negative_count=len(negative)
        )

        return similar, positive, negative


# Глобальный экземпляр (ленивая инициализация)
_vector_search: Optional[VectorSearch] = None


def get_vector_search() -> VectorSearch:
    """Получить экземпляр VectorSearch (singleton)."""
    global _vector_search

    if _vector_search is None:
        _vector_search = VectorSearch()

    return _vector_search
