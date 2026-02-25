"""
Analytics Module
Модуль для сбора и анализа метрик канала и лидов.

Функционал:
1. Статистика за период (публикации, реакции, engagement)
2. Топ лучших и худших постов
3. Анализ эффективности источников
4. Статистика по дням недели
5. Статистика векторной базы Qdrant
6. Аналитика лидов (конверсия, скоринг, источники)
7. ROI лид-магнита
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import text, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger()


class AnalyticsService:
    """Сервис для работы с аналитикой канала."""

    def __init__(self, db: AsyncSession):
        """
        Инициализация сервиса аналитики.

        Args:
            db: Асинхронная сессия базы данных
        """
        self.db = db

    async def get_period_stats(self, days: int = 7) -> Dict:
        """
        Получить общую статистику за период.

        Args:
            days: Количество дней для анализа

        Returns:
            Словарь с метриками
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            # Количество публикаций
            query_pubs = text("""
                SELECT COUNT(*) as total_publications
                FROM publications
                WHERE published_at >= :date_from
            """)
            result_pubs = await self.db.execute(query_pubs, {"date_from": date_from})
            total_pubs = result_pubs.scalar() or 0

            # Количество публикаций с реакциями (для engagement rate)
            query_engaged = text("""
                SELECT COUNT(*) as engaged_publications
                FROM publications
                WHERE published_at >= :date_from
                AND (
                    COALESCE((reactions->>'useful')::int, 0) +
                    COALESCE((reactions->>'important')::int, 0) +
                    COALESCE((reactions->>'controversial')::int, 0) +
                    COALESCE((reactions->>'banal')::int, 0) +
                    COALESCE((reactions->>'obvious')::int, 0) +
                    COALESCE((reactions->>'poor_quality')::int, 0) +
                    COALESCE((reactions->>'low_content_quality')::int, 0) +
                    COALESCE((reactions->>'bad_source')::int, 0)
                ) > 0
            """)
            result_engaged = await self.db.execute(query_engaged, {"date_from": date_from})
            engaged_pubs = result_engaged.scalar() or 0

            # Количество драфтов (одобренных и отклоненных)
            query_drafts = text("""
                SELECT
                    COUNT(*) as total_drafts,
                    COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_drafts,
                    COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_drafts
                FROM post_drafts
                WHERE created_at >= :date_from
            """)
            result_drafts = await self.db.execute(query_drafts, {"date_from": date_from})
            drafts_row = result_drafts.fetchone()

            total_drafts = drafts_row.total_drafts or 0
            approved_drafts = drafts_row.approved_drafts or 0
            rejected_drafts = drafts_row.rejected_drafts or 0

            # Агрегация реакций
            query_reactions = text("""
                SELECT
                    SUM(COALESCE((reactions->>'useful')::int, 0)) as useful,
                    SUM(COALESCE((reactions->>'important')::int, 0)) as important,
                    SUM(COALESCE((reactions->>'controversial')::int, 0)) as controversial,
                    SUM(COALESCE((reactions->>'banal')::int, 0)) as banal,
                    SUM(COALESCE((reactions->>'obvious')::int, 0)) as obvious,
                    SUM(COALESCE((reactions->>'poor_quality')::int, 0)) as poor_quality,
                    SUM(COALESCE((reactions->>'low_content_quality')::int, 0)) as low_content_quality,
                    SUM(COALESCE((reactions->>'bad_source')::int, 0)) as bad_source
                FROM publications
                WHERE published_at >= :date_from
            """)
            result_reactions = await self.db.execute(query_reactions, {"date_from": date_from})
            reactions_row = result_reactions.fetchone()

            reactions = {
                "useful": reactions_row.useful or 0,
                "important": reactions_row.important or 0,
                "controversial": reactions_row.controversial or 0,
                "banal": reactions_row.banal or 0,
                "obvious": reactions_row.obvious or 0,
                "poor_quality": reactions_row.poor_quality or 0,
                "low_content_quality": reactions_row.low_content_quality or 0,
                "bad_source": reactions_row.bad_source or 0
            }

            total_reactions = sum(reactions.values())

            # Средний quality score
            if total_pubs > 0:
                query_avg_score = text("""
                    SELECT AVG(
                        (
                            COALESCE((reactions->>'useful')::int, 0) +
                            COALESCE((reactions->>'important')::int, 0) -
                            COALESCE((reactions->>'banal')::int, 0) -
                            COALESCE((reactions->>'obvious')::int, 0) -
                            COALESCE((reactions->>'poor_quality')::int, 0) -
                            COALESCE((reactions->>'low_content_quality')::int, 0) -
                            COALESCE((reactions->>'bad_source')::int, 0)
                        )::float / NULLIF(
                            COALESCE((reactions->>'useful')::int, 0) +
                            COALESCE((reactions->>'important')::int, 0) +
                            COALESCE((reactions->>'banal')::int, 0) +
                            COALESCE((reactions->>'obvious')::int, 0) +
                            COALESCE((reactions->>'poor_quality')::int, 0) +
                            COALESCE((reactions->>'low_content_quality')::int, 0) +
                            COALESCE((reactions->>'bad_source')::int, 0) +
                            COALESCE((reactions->>'controversial')::int, 0),
                            0
                        )
                    ) as avg_quality_score
                    FROM publications
                    WHERE published_at >= :date_from
                    AND (
                        COALESCE((reactions->>'useful')::int, 0) +
                        COALESCE((reactions->>'important')::int, 0) +
                        COALESCE((reactions->>'banal')::int, 0) +
                        COALESCE((reactions->>'obvious')::int, 0) +
                        COALESCE((reactions->>'poor_quality')::int, 0) +
                        COALESCE((reactions->>'low_content_quality')::int, 0) +
                        COALESCE((reactions->>'bad_source')::int, 0) +
                        COALESCE((reactions->>'controversial')::int, 0)
                    ) > 0
                """)
                result_avg = await self.db.execute(query_avg_score, {"date_from": date_from})
                avg_quality_score = result_avg.scalar() or 0.0
            else:
                avg_quality_score = 0.0

            # Рассчитываем engagement rate
            engagement_rate = (engaged_pubs / total_pubs * 100) if total_pubs > 0 else 0

            return {
                "period_days": days,
                "total_publications": total_pubs,
                "engaged_publications": engaged_pubs,
                "engagement_rate": round(engagement_rate, 1),
                "total_drafts": total_drafts,
                "approved_drafts": approved_drafts,
                "rejected_drafts": rejected_drafts,
                "approval_rate": (approved_drafts / total_drafts * 100) if total_drafts > 0 else 0,
                "reactions": reactions,
                "total_reactions": total_reactions,
                "avg_quality_score": round(avg_quality_score, 2)
            }

        except Exception as e:
            logger.error("get_period_stats_error", error=str(e), days=days)
            raise

    async def get_top_posts(self, limit: int = 3, days: int = 7) -> List[Dict]:
        """
        Получить топ постов по quality score.

        Args:
            limit: Максимум результатов
            days: Количество дней для анализа

        Returns:
            Список постов с метриками
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            query = text("""
                SELECT
                    p.id,
                    d.title,
                    d.content,
                    p.published_at,
                    p.message_id as telegram_message_id,
                    p.reactions,
                    (
                        COALESCE((p.reactions->>'useful')::int, 0) +
                        COALESCE((p.reactions->>'important')::int, 0) -
                        COALESCE((p.reactions->>'banal')::int, 0) -
                        COALESCE((p.reactions->>'obvious')::int, 0) -
                        COALESCE((p.reactions->>'poor_quality')::int, 0)
                    )::float / NULLIF(
                        COALESCE((p.reactions->>'useful')::int, 0) +
                        COALESCE((p.reactions->>'important')::int, 0) +
                        COALESCE((p.reactions->>'banal')::int, 0) +
                        COALESCE((p.reactions->>'obvious')::int, 0) +
                        COALESCE((p.reactions->>'poor_quality')::int, 0) +
                        COALESCE((p.reactions->>'controversial')::int, 0),
                        0
                    ) as quality_score,
                    (
                        COALESCE((p.reactions->>'useful')::int, 0) +
                        COALESCE((p.reactions->>'important')::int, 0) +
                        COALESCE((p.reactions->>'banal')::int, 0) +
                        COALESCE((p.reactions->>'obvious')::int, 0) +
                        COALESCE((p.reactions->>'poor_quality')::int, 0) +
                        COALESCE((p.reactions->>'controversial')::int, 0)
                    ) as total_reactions
                FROM publications p
                JOIN post_drafts d ON p.draft_id = d.id
                WHERE p.published_at >= :date_from
                AND (
                    COALESCE((p.reactions->>'useful')::int, 0) +
                    COALESCE((p.reactions->>'important')::int, 0) +
                    COALESCE((p.reactions->>'banal')::int, 0) +
                    COALESCE((p.reactions->>'obvious')::int, 0) +
                    COALESCE((p.reactions->>'poor_quality')::int, 0) +
                    COALESCE((p.reactions->>'controversial')::int, 0)
                ) > 0
                ORDER BY quality_score DESC, total_reactions DESC
                LIMIT :limit
            """)

            result = await self.db.execute(query, {
                "date_from": date_from,
                "limit": limit
            })

            posts = []
            for row in result.fetchall():
                posts.append({
                    "id": row.id,
                    "title": row.title,
                    "content": row.content,
                    "published_at": row.published_at,
                    "telegram_message_id": row.telegram_message_id,
                    "reactions": row.reactions or {},
                    "quality_score": round(row.quality_score or 0, 2),
                    "total_reactions": row.total_reactions or 0
                })

            return posts

        except Exception as e:
            logger.error("get_top_posts_error", error=str(e), limit=limit, days=days)
            return []

    async def get_worst_posts(self, limit: int = 3, days: int = 7) -> List[Dict]:
        """
        Получить худшие посты по quality score.

        Args:
            limit: Максимум результатов
            days: Количество дней для анализа

        Returns:
            Список постов с метриками
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            query = text("""
                SELECT
                    p.id,
                    d.title,
                    d.content,
                    p.published_at,
                    p.message_id as telegram_message_id,
                    p.reactions,
                    (
                        COALESCE((p.reactions->>'useful')::int, 0) +
                        COALESCE((p.reactions->>'important')::int, 0) -
                        COALESCE((p.reactions->>'banal')::int, 0) -
                        COALESCE((p.reactions->>'obvious')::int, 0) -
                        COALESCE((p.reactions->>'poor_quality')::int, 0)
                    )::float / NULLIF(
                        COALESCE((p.reactions->>'useful')::int, 0) +
                        COALESCE((p.reactions->>'important')::int, 0) +
                        COALESCE((p.reactions->>'banal')::int, 0) +
                        COALESCE((p.reactions->>'obvious')::int, 0) +
                        COALESCE((p.reactions->>'poor_quality')::int, 0) +
                        COALESCE((p.reactions->>'controversial')::int, 0),
                        0
                    ) as quality_score,
                    (
                        COALESCE((p.reactions->>'useful')::int, 0) +
                        COALESCE((p.reactions->>'important')::int, 0) +
                        COALESCE((p.reactions->>'banal')::int, 0) +
                        COALESCE((p.reactions->>'obvious')::int, 0) +
                        COALESCE((p.reactions->>'poor_quality')::int, 0) +
                        COALESCE((p.reactions->>'controversial')::int, 0)
                    ) as total_reactions
                FROM publications p
                JOIN post_drafts d ON p.draft_id = d.id
                WHERE p.published_at >= :date_from
                AND (
                    COALESCE((p.reactions->>'banal')::int, 0) +
                    COALESCE((p.reactions->>'obvious')::int, 0) +
                    COALESCE((p.reactions->>'poor_quality')::int, 0)
                ) > 0
                ORDER BY quality_score ASC, total_reactions DESC
                LIMIT :limit
            """)

            result = await self.db.execute(query, {
                "date_from": date_from,
                "limit": limit
            })

            posts = []
            for row in result.fetchall():
                posts.append({
                    "id": row.id,
                    "title": row.title,
                    "content": row.content,
                    "published_at": row.published_at,
                    "telegram_message_id": row.telegram_message_id,
                    "reactions": row.reactions or {},
                    "quality_score": round(row.quality_score or 0, 2),
                    "total_reactions": row.total_reactions or 0
                })

            return posts

        except Exception as e:
            logger.error("get_worst_posts_error", error=str(e), limit=limit, days=days)
            return []

    async def get_source_stats(self, days: int = 7) -> List[Dict]:
        """
        Получить статистику по источникам.

        Args:
            days: Количество дней для анализа

        Returns:
            Список источников с метриками
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            # Статистика по сырым статьям (собрано новостей)
            query_raw = text("""
                SELECT
                    source_name,
                    COUNT(*) as total_collected
                FROM raw_articles
                WHERE fetched_at >= :date_from
                GROUP BY source_name
                ORDER BY total_collected DESC
            """)
            result_raw = await self.db.execute(query_raw, {"date_from": date_from})

            sources_collected = {}
            for row in result_raw.fetchall():
                sources_collected[row.source_name] = row.total_collected

            # Статистика по опубликованным постам
            query_pubs = text("""
                SELECT
                    a.source_name,
                    COUNT(*) as total_published,
                    AVG(
                        (
                            COALESCE((p.reactions->>'useful')::int, 0) +
                            COALESCE((p.reactions->>'important')::int, 0) -
                            COALESCE((p.reactions->>'banal')::int, 0) -
                            COALESCE((p.reactions->>'obvious')::int, 0) -
                            COALESCE((p.reactions->>'poor_quality')::int, 0)
                        )::float / NULLIF(
                            COALESCE((p.reactions->>'useful')::int, 0) +
                            COALESCE((p.reactions->>'important')::int, 0) +
                            COALESCE((p.reactions->>'banal')::int, 0) +
                            COALESCE((p.reactions->>'obvious')::int, 0) +
                            COALESCE((p.reactions->>'poor_quality')::int, 0) +
                            COALESCE((p.reactions->>'controversial')::int, 0),
                            0
                        )
                    ) as avg_quality_score
                FROM publications p
                JOIN post_drafts d ON p.draft_id = d.id
                JOIN raw_articles a ON d.article_id = a.id
                WHERE p.published_at >= :date_from
                GROUP BY a.source_name
            """)
            result_pubs = await self.db.execute(query_pubs, {"date_from": date_from})

            sources = []
            for row in result_pubs.fetchall():
                source_name = row.source_name
                total_collected = sources_collected.get(source_name, 0)
                total_published = row.total_published or 0

                sources.append({
                    "source_name": source_name,
                    "total_collected": total_collected,
                    "total_published": total_published,
                    "publication_rate": (total_published / total_collected * 100) if total_collected > 0 else 0,
                    "avg_quality_score": round(row.avg_quality_score or 0, 2)
                })

            # Сортировка по качеству
            sources.sort(key=lambda x: x["avg_quality_score"], reverse=True)

            return sources

        except Exception as e:
            logger.error("get_source_stats_error", error=str(e), days=days)
            return []

    async def get_weekday_stats(self, days: int = 30) -> Dict:
        """
        Получить статистику по дням недели.

        Args:
            days: Количество дней для анализа (минимум 7)

        Returns:
            Словарь с метриками по дням недели
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            query = text("""
                SELECT
                    EXTRACT(DOW FROM published_at) as day_of_week,
                    COUNT(*) as total_posts,
                    AVG(
                        (
                            COALESCE((reactions->>'useful')::int, 0) +
                            COALESCE((reactions->>'important')::int, 0) -
                            COALESCE((reactions->>'banal')::int, 0) -
                            COALESCE((reactions->>'obvious')::int, 0) -
                            COALESCE((reactions->>'poor_quality')::int, 0)
                        )::float / NULLIF(
                            COALESCE((reactions->>'useful')::int, 0) +
                            COALESCE((reactions->>'important')::int, 0) +
                            COALESCE((reactions->>'banal')::int, 0) +
                            COALESCE((reactions->>'obvious')::int, 0) +
                            COALESCE((reactions->>'poor_quality')::int, 0) +
                            COALESCE((reactions->>'controversial')::int, 0),
                            0
                        )
                    ) as avg_quality_score
                FROM publications
                WHERE published_at >= :date_from
                GROUP BY day_of_week
                ORDER BY day_of_week
            """)

            result = await self.db.execute(query, {"date_from": date_from})

            # Маппинг дней недели (0=Воскресенье, 1=Понедельник, ...)
            day_names = {
                0: "Вс",
                1: "Пн",
                2: "Вт",
                3: "Ср",
                4: "Чт",
                5: "Пт",
                6: "Сб"
            }

            weekday_stats = {}
            for row in result.fetchall():
                day_num = int(row.day_of_week)
                day_name = day_names.get(day_num, "??")

                weekday_stats[day_name] = {
                    "total_posts": row.total_posts or 0,
                    "avg_quality_score": round(row.avg_quality_score or 0, 2)
                }

            return weekday_stats

        except Exception as e:
            logger.error("get_weekday_stats_error", error=str(e), days=days)
            return {}

    async def get_vector_db_stats(self) -> Optional[Dict]:
        """
        Получить статистику векторной базы Qdrant.

        Returns:
            Словарь с метриками Qdrant или None если недоступен
        """
        try:
            from app.modules.vector_search import get_vector_search
            from app.config import settings

            if not getattr(settings, "qdrant_enabled", False):
                return None

            vector_search = get_vector_search()

            # Получить информацию о коллекции
            collection_info = vector_search.client.get_collection(
                collection_name=vector_search.COLLECTION_NAME
            )

            total_vectors = collection_info.points_count

            # Подсчитать векторы с разными quality_score
            # Scroll через все точки и агрегировать
            positive_count = 0
            negative_count = 0
            neutral_count = 0
            total_score = 0.0

            offset = None
            while True:
                results, next_offset = vector_search.client.scroll(
                    collection_name=vector_search.COLLECTION_NAME,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )

                if not results:
                    break

                for point in results:
                    quality_score = point.payload.get("quality_score", 0.0)
                    total_score += quality_score

                    if quality_score > 0.5:
                        positive_count += 1
                    elif quality_score < -0.3:
                        negative_count += 1
                    else:
                        neutral_count += 1

                offset = next_offset
                if offset is None:
                    break

            avg_score = (total_score / total_vectors) if total_vectors > 0 else 0.0

            return {
                "total_vectors": total_vectors,
                "positive_examples": positive_count,
                "negative_examples": negative_count,
                "neutral_examples": neutral_count,
                "avg_quality_score": round(avg_score, 2)
            }

        except Exception as e:
            logger.error("get_vector_db_stats_error", error=str(e))
            return None

    async def get_source_recommendations(self, days: int = 30) -> List[Dict]:
        """
        Получить рекомендации по источникам (какие стоит отключить).

        Args:
            days: Количество дней для анализа

        Returns:
            Список источников с рекомендациями
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            # Находим источники с низким качеством
            query = text("""
                SELECT
                    ra.source_name,
                    COUNT(p.id) as total_publications,
                    AVG(
                        (
                            COALESCE((p.reactions->>'useful')::int, 0) +
                            COALESCE((p.reactions->>'important')::int, 0) -
                            COALESCE((p.reactions->>'banal')::int, 0) -
                            COALESCE((p.reactions->>'obvious')::int, 0) -
                            COALESCE((p.reactions->>'poor_quality')::int, 0) -
                            COALESCE((p.reactions->>'low_content_quality')::int, 0) -
                            COALESCE((p.reactions->>'bad_source')::int, 0)
                        )::float / NULLIF(
                            COALESCE((p.reactions->>'useful')::int, 0) +
                            COALESCE((p.reactions->>'important')::int, 0) +
                            COALESCE((p.reactions->>'banal')::int, 0) +
                            COALESCE((p.reactions->>'obvious')::int, 0) +
                            COALESCE((p.reactions->>'poor_quality')::int, 0) +
                            COALESCE((p.reactions->>'low_content_quality')::int, 0) +
                            COALESCE((p.reactions->>'bad_source')::int, 0) +
                            COALESCE((p.reactions->>'controversial')::int, 0),
                            0
                        )
                    ) as avg_quality_score,
                    SUM(COALESCE((p.reactions->>'bad_source')::int, 0)) as bad_source_reactions,
                    SUM(COALESCE((p.reactions->>'low_content_quality')::int, 0)) as low_quality_reactions
                FROM publications p
                JOIN post_drafts pd ON p.draft_id = pd.id
                JOIN raw_articles ra ON pd.article_id = ra.id
                WHERE p.published_at >= :date_from
                GROUP BY ra.source_name
                HAVING COUNT(p.id) >= 2
            """)

            result = await self.db.execute(query, {"date_from": date_from})

            recommendations = []
            for row in result.fetchall():
                avg_score = row.avg_quality_score or 0.0
                bad_source_count = row.bad_source_reactions or 0
                low_quality_count = row.low_quality_reactions or 0
                total_pubs = row.total_publications

                # Определяем рекомендацию
                recommendation = None
                severity = None

                if avg_score < -0.4 and bad_source_count >= 2:
                    recommendation = "🚫 ОТКЛЮЧИТЬ: Ненадежный источник с низким качеством информации"
                    severity = "critical"
                elif avg_score < -0.3 and (bad_source_count >= 1 or low_quality_count >= 2):
                    recommendation = "⚠️ ПРОВЕРИТЬ: Источник с проблемами качества"
                    severity = "warning"
                elif avg_score < 0.0 and total_pubs >= 5:
                    recommendation = "💡 ПЕРЕСМОТРЕТЬ: Источник с отрицательными реакциями"
                    severity = "info"

                if recommendation:
                    recommendations.append({
                        "source_name": row.source_name,
                        "total_publications": total_pubs,
                        "avg_quality_score": round(avg_score, 2),
                        "bad_source_reactions": bad_source_count,
                        "low_quality_reactions": low_quality_count,
                        "recommendation": recommendation,
                        "severity": severity
                    })

            # Сортировка по серьезности (critical > warning > info)
            severity_order = {"critical": 0, "warning": 1, "info": 2}
            recommendations.sort(key=lambda x: (severity_order.get(x["severity"], 999), x["avg_quality_score"]))

            return recommendations

        except Exception as e:
            logger.error("get_source_recommendations_error", error=str(e), days=days)
            return []

    async def get_best_publish_time(self, days: int = 30) -> Dict:
        """
        Анализ: в какое время суток публикации получают больше всего engagement.
        A/B тестирование времени публикации.

        Args:
            days: Количество дней для анализа

        Returns:
            Словарь с рекомендациями по времени публикации
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            query = text("""
                SELECT
                    EXTRACT(HOUR FROM published_at) as hour_of_day,
                    COUNT(*) as total_posts,
                    AVG(views) as avg_views,
                    AVG(forwards) as avg_forwards,
                    AVG(
                        COALESCE((reactions->>'useful')::int, 0) +
                        COALESCE((reactions->>'important')::int, 0) +
                        COALESCE((reactions->>'controversial')::int, 0)
                    ) as avg_positive_reactions,
                    AVG(
                        (
                            COALESCE((reactions->>'useful')::int, 0) +
                            COALESCE((reactions->>'important')::int, 0) +
                            COALESCE((reactions->>'controversial')::int, 0)
                        )::float / NULLIF(views, 0)
                    ) as engagement_rate
                FROM publications
                WHERE published_at >= :date_from
                AND views > 0
                GROUP BY hour_of_day
                ORDER BY engagement_rate DESC
            """)

            result = await self.db.execute(query, {"date_from": date_from})

            hours_stats = []
            best_hour = None
            best_engagement = 0

            for row in result.fetchall():
                hour = int(row.hour_of_day)
                engagement_rate = row.engagement_rate or 0

                hours_stats.append({
                    "hour": hour,
                    "total_posts": row.total_posts,
                    "avg_views": round(row.avg_views or 0, 1),
                    "avg_forwards": round(row.avg_forwards or 0, 1),
                    "avg_positive_reactions": round(row.avg_positive_reactions or 0, 1),
                    "engagement_rate": round(engagement_rate * 100, 2)  # В процентах
                })

                if engagement_rate > best_engagement:
                    best_engagement = engagement_rate
                    best_hour = hour

            # Формируем рекомендацию
            if best_hour is not None:
                recommendation = f"Лучшее время для публикации: {best_hour:02d}:00-{(best_hour+1):02d}:00 MSK"
            else:
                recommendation = "Недостаточно данных для рекомендации"

            return {
                "best_hour": best_hour,
                "best_engagement_rate": round(best_engagement * 100, 2) if best_engagement else 0,
                "recommendation": recommendation,
                "hours_stats": hours_stats
            }

        except Exception as e:
            logger.error("get_best_publish_time_error", error=str(e), days=days)
            return {
                "best_hour": None,
                "best_engagement_rate": 0,
                "recommendation": "Ошибка анализа",
                "hours_stats": []
            }

    async def get_trending_topics(self, days: int = 7, top_n: int = 10) -> List[Dict]:
        """
        Анализ трендовых тем на основе топовых постов.
        Извлекает часто упоминаемые ключевые слова из заголовков.

        Args:
            days: Количество дней для анализа
            top_n: Количество топ-тем для возврата

        Returns:
            Список тем с частотой упоминаний
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            # Получаем топовые посты за период
            query = text("""
                SELECT
                    d.title,
                    d.content,
                    p.views,
                    (
                        COALESCE((p.reactions->>'useful')::int, 0) +
                        COALESCE((p.reactions->>'important')::int, 0)
                    ) as positive_reactions
                FROM publications p
                JOIN post_drafts d ON p.draft_id = d.id
                WHERE p.published_at >= :date_from
                AND p.views > 0
                ORDER BY positive_reactions DESC, p.views DESC
                LIMIT 30
            """)

            result = await self.db.execute(query, {"date_from": date_from})
            posts = result.fetchall()

            # Извлекаем ключевые слова из заголовков
            from collections import Counter
            import re

            # Стоп-слова (русские)
            stop_words = {
                "в", "и", "на", "с", "по", "для", "о", "от", "к", "у", "из", "за", "над",
                "под", "при", "что", "как", "это", "весь", "свой", "все", "мой", "наш", "ваш",
                "их", "его", "её", "этот", "тот", "был", "быть", "есть", "нет", "не", "ни",
                "чем", "где", "куда", "когда", "почему", "или", "но", "а", "да"
            }

            words = []
            for post in posts:
                # Извлекаем слова из заголовка (min 4 символа)
                title_words = re.findall(r'\b[а-яёА-ЯЁa-zA-Z]{4,}\b', post.title.lower())
                words.extend([w for w in title_words if w not in stop_words])

            # Подсчитываем частоту
            word_counts = Counter(words)
            trending = []

            for word, count in word_counts.most_common(top_n):
                trending.append({
                    "topic": word.capitalize(),
                    "mentions": count,
                    "relevance_score": round(count / len(posts) * 100, 1) if posts else 0
                })

            return trending

        except Exception as e:
            logger.error("get_trending_topics_error", error=str(e), days=days)
            return []

    async def get_performance_alerts(self, days: int = 7) -> List[Dict]:
        """
        Проверка метрик и генерация алертов о проблемах.

        Args:
            days: Количество дней для анализа

        Returns:
            Список алертов с описанием проблем
        """
        try:
            alerts = []

            # 1. Проверка: Engagement rate упал > 20%
            stats_current = await self.get_period_stats(days)
            stats_previous = await self.get_period_stats(days * 2)  # Предыдущий период

            if stats_previous['engagement_rate'] > 0:
                engagement_drop = (
                    (stats_previous['engagement_rate'] - stats_current['engagement_rate']) /
                    stats_previous['engagement_rate'] * 100
                )

                if engagement_drop > 20:
                    alerts.append({
                        "severity": "warning",
                        "type": "engagement_drop",
                        "message": f"⚠️ Engagement rate упал на {engagement_drop:.1f}% за последнюю неделю",
                        "details": f"Было: {stats_previous['engagement_rate']:.1f}%, Сейчас: {stats_current['engagement_rate']:.1f}%"
                    })

            # 2. Проверка: Источники с плохим качеством
            bad_sources = await self.get_source_recommendations(days)
            critical_sources = [s for s in bad_sources if s.get("severity") == "critical"]

            if critical_sources:
                source_names = ", ".join([s["source_name"] for s in critical_sources[:3]])
                alerts.append({
                    "severity": "critical",
                    "type": "bad_sources",
                    "message": f"🚫 Найдены источники с критическим качеством",
                    "details": f"Источники: {source_names}"
                })

            # 3. Проверка: Низкий approval rate
            if stats_current['approval_rate'] < 50:
                alerts.append({
                    "severity": "info",
                    "type": "low_approval",
                    "message": f"💡 Низкий approval rate: {stats_current['approval_rate']:.1f}%",
                    "details": f"Одобрено {stats_current['approved_drafts']} из {stats_current['total_drafts']} драфтов"
                })

            # 4. Проверка: Нет публикаций за последние 3 дня
            if stats_current['total_publications'] == 0 and days >= 3:
                alerts.append({
                    "severity": "critical",
                    "type": "no_publications",
                    "message": "🚫 Нет публикаций за последние дни",
                    "details": "Проверьте работу автоматического workflow"
                })

            return alerts

        except Exception as e:
            logger.error("get_performance_alerts_error", error=str(e), days=days)
            return []

    async def get_views_and_forwards_stats(self, days: int = 7) -> Dict:
        """
        Статистика по views и forwards (доступно после сбора метрик из Telegram).

        Args:
            days: Количество дней для анализа

        Returns:
            Словарь со статистикой views/forwards
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            query = text("""
                SELECT
                    COUNT(*) as total_posts,
                    SUM(views) as total_views,
                    SUM(forwards) as total_forwards,
                    AVG(views) as avg_views,
                    AVG(forwards) as avg_forwards,
                    MAX(views) as max_views,
                    MAX(forwards) as max_forwards
                FROM publications
                WHERE published_at >= :date_from
                AND views > 0
            """)

            result = await self.db.execute(query, {"date_from": date_from})
            row = result.fetchone()

            if row and row.total_posts > 0:
                return {
                    "total_posts": row.total_posts,
                    "total_views": row.total_views or 0,
                    "total_forwards": row.total_forwards or 0,
                    "avg_views": round(row.avg_views or 0, 1),
                    "avg_forwards": round(row.avg_forwards or 0, 1),
                    "max_views": row.max_views or 0,
                    "max_forwards": row.max_forwards or 0,
                    "viral_coefficient": round((row.total_forwards or 0) / (row.total_views or 1) * 100, 2)  # % постов которые форвардят
                }
            else:
                return {
                    "total_posts": 0,
                    "total_views": 0,
                    "total_forwards": 0,
                    "avg_views": 0,
                    "avg_forwards": 0,
                    "max_views": 0,
                    "max_forwards": 0,
                    "viral_coefficient": 0
                }

        except Exception as e:
            logger.error("get_views_and_forwards_stats_error", error=str(e), days=days)
            return {
                "total_posts": 0,
                "total_views": 0,
                "total_forwards": 0,
                "avg_views": 0,
                "avg_forwards": 0,
                "max_views": 0,
                "max_forwards": 0,
                "viral_coefficient": 0
            }

    async def get_ai_analysis_stats(self) -> Dict:
        """Статистика использования AI анализа (токены и стоимость) с разбивкой по моделям."""
        try:
            from datetime import date
            from dateutil.relativedelta import relativedelta

            today = date.today()
            month_start = date(today.year, today.month, 1)
            year_start = date(today.year, 1, 1)

            # Статистика за текущий месяц
            query_month = text("""
                SELECT
                    COUNT(*) as count,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as total_cost
                FROM api_usage
                WHERE operation = 'ai_analysis'
                AND date >= :month_start
            """)

            result_month = await self.db.execute(query_month, {"month_start": month_start})
            row_month = result_month.fetchone()

            # Статистика за текущий год
            query_year = text("""
                SELECT
                    COUNT(*) as count,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as total_cost
                FROM api_usage
                WHERE operation = 'ai_analysis'
                AND date >= :year_start
            """)

            result_year = await self.db.execute(query_year, {"year_start": year_start})
            row_year = result_year.fetchone()

            # Разбивка по моделям за месяц
            query_month_by_model = text("""
                SELECT
                    model,
                    COUNT(*) as count,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as total_cost
                FROM api_usage
                WHERE operation = 'ai_analysis'
                AND date >= :month_start
                GROUP BY model
            """)

            result_month_by_model = await self.db.execute(query_month_by_model, {"month_start": month_start})
            by_model_month = {}
            for row in result_month_by_model.fetchall():
                by_model_month[row.model] = {
                    "count": row.count,
                    "tokens": row.total_tokens or 0,
                    "cost_usd": float(row.total_cost or 0)
                }

            # Разбивка по моделям за год
            query_year_by_model = text("""
                SELECT
                    model,
                    COUNT(*) as count,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as total_cost
                FROM api_usage
                WHERE operation = 'ai_analysis'
                AND date >= :year_start
                GROUP BY model
            """)

            result_year_by_model = await self.db.execute(query_year_by_model, {"year_start": year_start})
            by_model_year = {}
            for row in result_year_by_model.fetchall():
                by_model_year[row.model] = {
                    "count": row.count,
                    "tokens": row.total_tokens or 0,
                    "cost_usd": float(row.total_cost or 0)
                }

            return {
                "month": {
                    "count": row_month.count or 0,
                    "total_tokens": row_month.total_tokens or 0,
                    "total_cost_usd": float(row_month.total_cost or 0),
                    "by_model": by_model_month
                },
                "year": {
                    "count": row_year.count or 0,
                    "total_tokens": row_year.total_tokens or 0,
                    "total_cost_usd": float(row_year.total_cost or 0),
                    "by_model": by_model_year
                }
            }

        except Exception as e:
            logger.error("get_ai_analysis_stats_error", error=str(e))
            return {
                "month": {"count": 0, "total_tokens": 0, "total_cost_usd": 0, "by_model": {}},
                "year": {"count": 0, "total_tokens": 0, "total_cost_usd": 0, "by_model": {}}
            }

    async def get_channel_conversion_stats(self, days: int = 30) -> Dict:
        """
        Получить статистику конверсии из канала.

        Отслеживает переходы пользователей из Telegram канала в Mini App:
        - Общее количество переходов
        - Уникальные пользователи
        - Просмотры статей из канала
        - ТОП статей по переходам

        Args:
            days: Количество дней для анализа (по умолчанию 30)

        Returns:
            Словарь со статистикой конверсии
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            # 1. Общая статистика переходов из канала
            query_totals = text("""
                SELECT
                    COUNT(*) as total_interactions,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(CASE WHEN source = 'channel' THEN 1 END) as channel_clicks,
                    COUNT(CASE WHEN source = 'channel_article' THEN 1 END) as article_views_from_channel,
                    COUNT(CASE WHEN source IN ('channel', 'channel_article') THEN 1 END) as total_from_channel
                FROM user_interactions
                WHERE created_at >= :date_from
                AND source IN ('channel', 'channel_article')
            """)

            result_totals = await self.db.execute(query_totals, {"date_from": date_from})
            row_totals = result_totals.fetchone()

            # 2. ТОП-10 статей по переходам из канала
            query_top_articles = text("""
                SELECT
                    p.id,
                    d.title,
                    COUNT(*) as views_from_channel,
                    COUNT(DISTINCT ui.user_id) as unique_users,
                    p.published_at
                FROM user_interactions ui
                JOIN publications p ON ui.publication_id = p.id
                JOIN post_drafts d ON p.draft_id = d.id
                WHERE ui.created_at >= :date_from
                AND ui.source IN ('channel', 'channel_article')
                AND ui.publication_id IS NOT NULL
                GROUP BY p.id, d.title, p.published_at
                ORDER BY views_from_channel DESC, unique_users DESC
                LIMIT 10
            """)

            result_articles = await self.db.execute(query_top_articles, {"date_from": date_from})

            top_articles = []
            for row in result_articles.fetchall():
                top_articles.append({
                    "publication_id": row.id,
                    "title": row.title,
                    "views_from_channel": row.views_from_channel,
                    "unique_users": row.unique_users,
                    "published_at": row.published_at.isoformat() if row.published_at else None
                })

            # 3. Статистика по дням (последние 7 дней)
            query_daily = text("""
                SELECT
                    DATE(created_at) as date,
                    COUNT(CASE WHEN source = 'channel' THEN 1 END) as channel_clicks,
                    COUNT(CASE WHEN source = 'channel_article' THEN 1 END) as article_views,
                    COUNT(DISTINCT user_id) as unique_users
                FROM user_interactions
                WHERE created_at >= :week_ago
                AND source IN ('channel', 'channel_article')
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                LIMIT 7
            """)

            week_ago = datetime.utcnow() - timedelta(days=7)
            result_daily = await self.db.execute(query_daily, {"week_ago": week_ago})

            daily_stats = []
            for row in result_daily.fetchall():
                daily_stats.append({
                    "date": row.date.isoformat() if row.date else None,
                    "channel_clicks": row.channel_clicks,
                    "article_views": row.article_views,
                    "unique_users": row.unique_users
                })

            return {
                "period_days": days,
                "total_interactions": row_totals.total_interactions or 0,
                "unique_users": row_totals.unique_users or 0,
                "channel_clicks": row_totals.channel_clicks or 0,
                "article_views_from_channel": row_totals.article_views_from_channel or 0,
                "total_from_channel": row_totals.total_from_channel or 0,
                "conversion_rate": round(
                    (row_totals.article_views_from_channel / row_totals.channel_clicks * 100)
                    if row_totals.channel_clicks and row_totals.channel_clicks > 0
                    else 0,
                    2
                ),
                "top_articles": top_articles,
                "daily_stats": daily_stats
            }

        except Exception as e:
            logger.error("get_channel_conversion_stats_error", error=str(e))
            return {
                "period_days": days,
                "total_interactions": 0,
                "unique_users": 0,
                "channel_clicks": 0,
                "article_views_from_channel": 0,
                "total_from_channel": 0,
                "conversion_rate": 0,
                "top_articles": [],
                "daily_stats": []
            }

    # ==================== Lead Analytics ====================

    async def get_lead_analytics(self, days: int = 30) -> Dict:
        """
        Получить аналитику по лидам за период.

        Args:
            days: Количество дней для анализа

        Returns:
            Словарь с метриками лидов
        """
        try:
            date_from = datetime.utcnow() - timedelta(days=days)

            # Общая статистика лидов
            query_total = text("""
                SELECT
                    COUNT(*) as total_leads,
                    COUNT(CASE WHEN lead_status = 'qualified' THEN 1 END) as qualified_leads,
                    COUNT(CASE WHEN lead_status = 'converted' THEN 1 END) as converted_leads,
                    COUNT(CASE WHEN lead_magnet_completed = true THEN 1 END) as completed_magnet,
                    AVG(lead_score) as avg_lead_score,
                    COUNT(CASE WHEN email IS NOT NULL THEN 1 END) as with_email,
                    COUNT(CASE WHEN phone IS NOT NULL THEN 1 END) as with_phone,
                    COUNT(CASE WHEN company IS NOT NULL THEN 1 END) as with_company
                FROM lead_profiles
                WHERE created_at >= :date_from
            """)

            result_total = await self.db.execute(query_total, {"date_from": date_from})
            total_row = result_total.fetchone()

            # Конверсия по дням
            query_daily = text("""
                SELECT
                    DATE(created_at) as date,
                    COUNT(*) as new_leads,
                    COUNT(CASE WHEN lead_magnet_completed = true THEN 1 END) as completed_magnet,
                    COUNT(CASE WHEN lead_status = 'qualified' THEN 1 END) as qualified,
                    AVG(lead_score) as avg_score
                FROM lead_profiles
                WHERE created_at >= :date_from
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at) DESC
                LIMIT 30
            """)

            result_daily = await self.db.execute(query_daily, {"date_from": date_from})
            daily_stats = [
                {
                    "date": str(row.date),
                    "new_leads": row.new_leads or 0,
                    "completed_magnet": row.completed_magnet or 0,
                    "qualified": row.qualified or 0,
                    "avg_score": round(float(row.avg_score or 0), 1)
                }
                for row in result_daily.fetchall()
            ]

            # Топ лидов по скорингу
            query_top_leads = text("""
                SELECT
                    lp.user_id,
                    lp.email,
                    lp.company,
                    lp.lead_score,
                    lp.expertise_level,
                    lp.business_focus,
                    lp.created_at,
                    up.username,
                    up.full_name
                FROM lead_profiles lp
                JOIN user_profiles up ON lp.user_id = up.user_id
                WHERE lp.created_at >= :date_from AND lp.lead_score > 0
                ORDER BY lp.lead_score DESC
                LIMIT 10
            """)

            result_top = await self.db.execute(query_top_leads, {"date_from": date_from})
            top_leads = [
                {
                    "user_id": row.user_id,
                    "username": row.username,
                    "full_name": row.full_name,
                    "email": row.email,
                    "company": row.company,
                    "lead_score": row.lead_score,
                    "expertise_level": row.expertise_level,
                    "business_focus": row.business_focus,
                    "created_at": str(row.created_at.date())
                }
                for row in result_top.fetchall()
            ]

            # Статистика по источникам привлечения
            query_sources = text("""
                SELECT
                    business_focus as source,
                    COUNT(*) as count,
                    AVG(lead_score) as avg_score,
                    COUNT(CASE WHEN lead_magnet_completed = true THEN 1 END) as completed
                FROM lead_profiles
                WHERE created_at >= :date_from AND business_focus IS NOT NULL
                GROUP BY business_focus
                ORDER BY count DESC
            """)

            result_sources = await self.db.execute(query_sources, {"date_from": date_from})
            sources_stats = [
                {
                    "source": row.source,
                    "count": row.count,
                    "avg_score": round(float(row.avg_score or 0), 1),
                    "completed_rate": round((row.completed / row.count * 100) if row.count > 0 else 0, 1)
                }
                for row in result_sources.fetchall()
            ]

            # Рассчитываем метрики конверсии
            total_leads = total_row.total_leads or 0
            qualified_leads = total_row.qualified_leads or 0
            converted_leads = total_row.converted_leads or 0
            completed_magnet = total_row.completed_magnet or 0

            qualification_rate = (qualified_leads / total_leads * 100) if total_leads > 0 else 0
            conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
            magnet_completion_rate = (completed_magnet / total_leads * 100) if total_leads > 0 else 0

            return {
                "period_days": days,
                "overview": {
                    "total_leads": total_leads,
                    "qualified_leads": qualified_leads,
                    "converted_leads": converted_leads,
                    "completed_magnet": completed_magnet,
                    "qualification_rate": round(qualification_rate, 1),
                    "conversion_rate": round(conversion_rate, 1),
                    "magnet_completion_rate": round(magnet_completion_rate, 1),
                    "avg_lead_score": round(float(total_row.avg_lead_score or 0), 1),
                    "with_email": total_row.with_email or 0,
                    "with_phone": total_row.with_phone or 0,
                    "with_company": total_row.with_company or 0
                },
                "daily_stats": daily_stats,
                "top_leads": top_leads,
                "sources_stats": sources_stats
            }

        except Exception as e:
            logger.error("get_lead_analytics_error", error=str(e))
            return {
                "period_days": days,
                "overview": {
                    "total_leads": 0,
                    "qualified_leads": 0,
                    "converted_leads": 0,
                    "completed_magnet": 0,
                    "qualification_rate": 0,
                    "conversion_rate": 0,
                    "magnet_completion_rate": 0,
                    "avg_lead_score": 0,
                    "with_email": 0,
                    "with_phone": 0,
                    "with_company": 0
                },
                "daily_stats": [],
                "top_leads": [],
                "sources_stats": []
            }

    async def get_lead_magnet_roi(self, days: int = 30) -> Dict:
        """
        Рассчитать ROI лид-магнита.

        Args:
            days: Период для анализа

        Returns:
            Метрики ROI лид-магнита
        """
        try:
            # Получаем стоимость API за период
            api_cost_query = text("""
                SELECT COALESCE(SUM(cost), 0) as total_cost
                FROM api_usage_tracking
                WHERE created_at >= :date_from
                AND operation_type IN ('openai_completion', 'perplexity_completion')
            """)

            date_from = datetime.utcnow() - timedelta(days=days)
            result = await self.db.execute(api_cost_query, {"date_from": date_from})
            total_api_cost = float(result.scalar() or 0)

            # Получаем статистику лидов
            leads_query = text("""
                SELECT
                    COUNT(*) as total_leads,
                    COUNT(CASE WHEN lead_status IN ('qualified', 'converted') THEN 1 END) as quality_leads,
                    AVG(lead_score) as avg_score
                FROM lead_profiles
                WHERE created_at >= :date_from
            """)

            result = await self.db.execute(leads_query, {"date_from": date_from})
            leads_row = result.fetchone()

            total_leads = leads_row.total_leads or 0
            quality_leads = leads_row.quality_leads or 0
            avg_score = float(leads_row.avg_score or 0)

            # Предполагаемая ценность лида (можно настроить)
            assumed_lead_value = 500  # рублей за качественного лида
            quality_lead_value = quality_leads * assumed_lead_value

            # ROI = (Прибыль - Затраты) / Затраты * 100%
            profit = quality_lead_value - total_api_cost
            roi = (profit / total_api_cost * 100) if total_api_cost > 0 else 0

            return {
                "period_days": days,
                "costs": {
                    "api_cost": round(total_api_cost, 2),
                    "total_cost": round(total_api_cost, 2)  # можно добавить другие затраты
                },
                "revenue": {
                    "total_leads": total_leads,
                    "quality_leads": quality_leads,
                    "assumed_lead_value": assumed_lead_value,
                    "estimated_revenue": quality_lead_value
                },
                "metrics": {
                    "profit": round(profit, 2),
                    "roi_percent": round(roi, 1),
                    "cost_per_lead": round(total_api_cost / total_leads, 2) if total_leads > 0 else 0,
                    "cost_per_quality_lead": round(total_api_cost / quality_leads, 2) if quality_leads > 0 else 0,
                    "avg_lead_score": round(avg_score, 1)
                }
            }

        except Exception as e:
            logger.error("get_lead_magnet_roi_error", error=str(e))
            return {
                "period_days": days,
                "costs": {"api_cost": 0, "total_cost": 0},
                "revenue": {"total_leads": 0, "quality_leads": 0, "estimated_revenue": 0},
                "metrics": {"profit": 0, "roi_percent": 0, "cost_per_lead": 0, "cost_per_quality_lead": 0}
            }
