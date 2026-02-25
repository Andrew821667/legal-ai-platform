"""
Celery Tasks
Асинхронные задачи для автоматизации workflow.

Расписание:
- 09:00 MSK - ежедневный сбор и обработка новостей
- 17:00 MSK (пятница) - еженедельный подкаст (Phase 2+)
"""

import asyncio
import sys

# КРИТИЧНО: Отключаем uvloop для Celery worker
# uvloop привязывается к event loop и вызывает "Event loop is closed" при asyncio.run()
# Устанавливаем стандартную asyncio policy до любых импортов asyncpg
if 'celery' in sys.argv[0] or 'celery' in ' '.join(sys.argv):
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

from datetime import datetime, timedelta
from typing import Dict, Any

from celery import Celery
from celery.schedules import crontab
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.fetcher import fetch_news
from app.modules.cleaner import clean_news
from app.modules.ai_core import process_articles_with_ai
from app.modules.media_factory import create_media_for_drafts
# НЕ импортируем bot и send_draft_for_review здесь!
# Bot() создаёт aiohttp клиент который привязывается к event loop
# Импортируем их внутри async функций где они нужны
from app.models.database import PostDraft

import structlog

logger = structlog.get_logger()


# Инициализация Celery
app = Celery('legal_ai_news')

# Конфигурация Celery
app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=settings.celery_accept_content,
    timezone=settings.celery_timezone,
    enable_utc=settings.celery_enable_utc,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    # КРИТИЧНО: Принудительная установка threads pool
    worker_pool='threads',
    worker_concurrency=1,
)


# ====================
# Celery Worker Startup Hook
# ====================

@app.on_after_configure.connect
def setup_database_tables(sender, **kwargs):
    """
    Инициализация таблиц БД при запуске Celery worker.
    Создаёт все таблицы если их ещё нет в базе данных.
    """
    async def _init_db():
        from app.models.database import init_db
        try:
            await init_db()
            logger.info("celery_database_initialized")
        except Exception as e:
            logger.error("celery_database_init_error", error=str(e))

    # Запускаем инициализацию БД
    asyncio.run(_init_db())


# ====================
# Утилитарные функции
# ====================

def run_async(coro):
    """
    Запустить асинхронную корутину в синхронном контексте.
    Использует asyncio.run() для чистого выполнения (Python 3.11+).

    Args:
        coro: Корутина для выполнения

    Returns:
        Результат выполнения
    """
    # asyncio.run() автоматически создаёт новый event loop,
    # выполняет корутину и ПРАВИЛЬНО закрывает все ресурсы
    return asyncio.run(coro)


async def notify_admin(message: str, bot=None):
    """
    Отправить уведомление администратору.

    Args:
        message: Текст уведомления
        bot: Опциональный экземпляр Bot (для использования в Celery tasks)
    """
    try:
        # Проверяем что admin_id установлен
        if not settings.telegram_admin_id or settings.telegram_admin_id == 0:
            logger.warning("notify_admin_no_admin_id", admin_id=settings.telegram_admin_id)
            return

        if bot is None:
            # Импортируем get_bot ЗДЕСЬ чтобы избежать создания aiohttp клиента при импорте модуля
            from app.bot.handlers import get_bot
            bot = get_bot()

        await bot.send_message(
            chat_id=settings.telegram_admin_id,
            text=message,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("admin_notification_error", error=str(e), exc_info=True)


# ====================
# Задачи
# ====================

async def send_fetch_statistics(stats: dict):
    """
    Отправить детальную статистику сбора новостей администратору.

    Args:
        stats: Словарь с количеством новостей по источникам
    """
    try:
        logger.info("send_fetch_statistics_started", stats_keys=list(stats.keys()) if stats else [])

        from app.bot.handlers import get_bot
        from app.config import settings

        total_articles = sum(stats.values())
        source_count = len(stats)

        logger.info("send_fetch_statistics_counts", total=total_articles, sources=source_count)

        # Формируем детальное сообщение
        message = "📊 <b>Статистика сбора новостей</b>\n\n"

        message += f"📰 <b>Всего собрано:</b> {total_articles} статей\n"
        message += f"📡 <b>Источников обработано:</b> {source_count}\n\n"

        if stats:
            message += "📋 <b>По источникам:</b>\n"
            # Сортируем по количеству (от большего к меньшему)
            sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)

            for source_name, count in sorted_stats:
                if count > 0:
                    message += f"  ✅ <b>{source_name}:</b> {count} шт.\n"
                else:
                    message += f"  ⚠️ <b>{source_name}:</b> нет новых\n"

            # Топ-3 источника
            top_sources = sorted_stats[:3]
            if top_sources and top_sources[0][1] > 0:
                message += f"\n🏆 <b>Топ-3 источника:</b>\n"
                for i, (source_name, count) in enumerate(top_sources, 1):
                    if count > 0:
                        message += f"  {i}. {source_name} ({count})\n"
        else:
            message += "⚠️ <i>Новости не найдены</i>\n"

        message += f"\n⏱️ <i>Время сбора: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</i>"

        # Проверяем что admin_id установлен
        if not settings.telegram_admin_id or settings.telegram_admin_id == 0:
            logger.warning("send_fetch_statistics_no_admin_id", admin_id=settings.telegram_admin_id)
            return

        logger.info("send_fetch_statistics_getting_bot")
        bot = get_bot()

        logger.info("send_fetch_statistics_sending", admin_id=settings.telegram_admin_id, message_length=len(message))
        await bot.send_message(
            chat_id=settings.telegram_admin_id,
            text=message,
            parse_mode="HTML"
        )

        logger.info("fetch_statistics_sent", total=total_articles, sources=source_count)

    except Exception as e:
        logger.error("send_fetch_statistics_error", error=str(e), exc_info=True)
        # Не падаем если статистика не отправилась
        # Но пробуем отправить уведомление об ошибке админу
        try:
            await notify_admin(
                f"⚠️ <b>Ошибка отправки статистики сбора</b>\n\n"
                f"Ошибка: {str(e)}\n\n"
                f"Проверьте логи для деталей."
            )
        except:
            pass  # Если даже notify_admin не работает, молча пропускаем


@app.task(max_retries=3, autoretry_for=(Exception,), retry_backoff=60, retry_backoff_max=600)
def fetch_news_task():
    """
    Задача сбора новостей из всех источников.

    Запуск: ежедневно в 09:00 MSK
    """
    logger.info("fetch_news_task_started")

    async def fetch():
        # Создаём новый engine внутри asyncio.run() контекста
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import NullPool
        from app.config import settings

        # КРИТИЧНО: Используем NullPool вместо обычного пула
        # NullPool НЕ кэширует соединения и закрывает их сразу
        # Это предотвращает RuntimeError: Event loop is closed при garbage collection
        engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            poolclass=NullPool,  # Отключаем пул соединений
        )

        SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        try:
            async with SessionLocal() as session:
                stats = await fetch_news(session)

            # Логируем статистику перед отправкой
            logger.info("fetch_completed_sending_stats", stats=stats, total=sum(stats.values() if stats else []))

            # Отправляем статистику админу
            await send_fetch_statistics(stats)

            return stats
        finally:
            # Закрываем engine ДО выхода из asyncio.run()
            await engine.dispose()

    stats = run_async(fetch())

    logger.info("fetch_news_task_completed", stats=stats)

    # НЕ используем log_to_db в Celery - она использует глобальный AsyncSessionLocal
    # который привязан к старому event loop
    # Вместо этого логируем только в structlog

    return f"Fetched {sum(stats.values())} articles from {len(stats)} sources"


@app.task(max_retries=3, autoretry_for=(Exception,), retry_backoff=60, retry_backoff_max=600)
def clean_news_task():
    """
    Задача фильтрации и дедупликации новостей.

    Запуск: ежедневно в 09:10 MSK (через 10 минут после fetch)
    """
    logger.info("clean_news_task_started")

    async def clean():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import NullPool
        from app.config import settings

        engine = create_async_engine(
            settings.database_url,
            poolclass=NullPool,
        )

        SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        try:
            async with SessionLocal() as session:
                stats = await clean_news(session)
            return stats
        finally:
            await engine.dispose()

    stats = run_async(clean())

    logger.info("clean_news_task_completed", stats=stats)

    # НЕ используем log_to_db - она использует глобальный AsyncSessionLocal

    return f"Filtered: {stats['filtered']}, Rejected: {stats['rejected']}"


@app.task(max_retries=3, autoretry_for=(Exception,), retry_backoff=60, retry_backoff_max=600)
def analyze_articles_task():
    """
    Задача AI анализа и генерации драфтов.

    Запуск: ежедневно в 09:15 MSK (через 15 минут после fetch)
    """
    logger.info("analyze_articles_task_started")

    async def analyze():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import NullPool
        from app.config import settings

        engine = create_async_engine(
            settings.database_url,
            poolclass=NullPool,
        )

        SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        try:
            async with SessionLocal() as session:
                stats = await process_articles_with_ai(session)
            return stats
        finally:
            await engine.dispose()

    stats = run_async(analyze())

    logger.info("analyze_articles_task_completed", stats=stats)

    # НЕ используем log_to_db - она использует глобальный AsyncSessionLocal

    return f"Created {stats['drafts_created']} drafts"


@app.task(max_retries=3, autoretry_for=(Exception,), retry_backoff=60, retry_backoff_max=600)
def generate_media_task():
    """
    Задача генерации медиа (обложек) для драфтов.

    Запуск: ежедневно в 09:20 MSK (через 20 минут после fetch)
    """
    logger.info("generate_media_task_started")

    async def generate():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.pool import NullPool
        from app.config import settings

        engine = create_async_engine(
            settings.database_url,
            poolclass=NullPool,
        )

        SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        try:
            async with SessionLocal() as session:
                count = await create_media_for_drafts(session)
            return count
        finally:
            await engine.dispose()

    count = run_async(generate())

    logger.info("generate_media_task_completed", count=count)

    return f"Generated {count} covers"


@app.task(max_retries=2, autoretry_for=(Exception,), retry_backoff=120)
def send_drafts_to_admin_task():
    """
    Задача отправки драфтов администратору на модерацию.

    Запускается независимо от основного workflow через 25 минут после старта.
    Имеет retry механизм для надёжности.
    """
    try:
        logger.info("send_drafts_to_admin_task_started")

        async def send_drafts():
            from datetime import timedelta
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
            from sqlalchemy.pool import NullPool
            from sqlalchemy import select, and_
            from app.config import settings
            from aiogram import Bot
            # Импортируем send_draft_for_review ЗДЕСЬ чтобы избежать создания Bot() при импорте модуля
            from app.bot.handlers import send_draft_for_review

            # Создаём Bot ВНУТРИ asyncio.run() контекста
            # чтобы aiohttp клиент привязался к правильному event loop
            bot = Bot(token=settings.telegram_bot_token)

            engine = create_async_engine(
                settings.database_url,
                poolclass=NullPool,
            )

            SessionLocal = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            sent_count = 0
            error_count = 0

            try:
                async with SessionLocal() as session:
                    # Получаем только недавно созданные драфты (за последние 2 часа)
                    # Это предотвращает повторную отправку уже отправленных драфтов
                    two_hours_ago = datetime.utcnow() - timedelta(hours=2)

                    result = await session.execute(
                        select(PostDraft)
                        .where(
                            and_(
                                PostDraft.status == 'pending_review',
                                PostDraft.created_at >= two_hours_ago
                            )
                        )
                        .order_by(PostDraft.created_at.desc())
                    )
                    drafts = list(result.scalars().all())

                    logger.info("drafts_found", count=len(drafts))

                    if not drafts:
                        # Просто логируем, не беспокоим админа
                        logger.info("no_drafts_to_send", reason="no_pending_drafts_in_last_2_hours")
                        return 0

                    # Отправляем уведомление о количестве драфтов
                    await notify_admin(
                        f"📝 <b>Новые драфты готовы к модерации!</b>\n\n"
                        f"Количество: {len(drafts)}\n\n"
                        f"Сейчас начну отправку...",
                        bot=bot
                    )

                    # Отправляем каждый драфт (ограничиваем настройкой publisher_max_posts_per_day)
                    max_drafts = min(len(drafts), settings.publisher_max_posts_per_day)
                    logger.info("sending_drafts", total=len(drafts), max_to_send=max_drafts)

                    for index, draft in enumerate(drafts[:max_drafts], start=1):
                        try:
                            await send_draft_for_review(
                                settings.telegram_admin_id,
                                draft,
                                session,
                                bot=bot,
                                draft_number=index  # Порядковый номер за день
                            )
                            sent_count += 1
                            logger.info("draft_sent", draft_id=draft.id, index=index)
                            await asyncio.sleep(1)  # Rate limiting
                        except Exception as e:
                            error_count += 1
                            logger.error("draft_send_error", draft_id=draft.id, error=str(e), index=index)
                            # Продолжаем отправку следующих драфтов даже если один упал

                    # Финальное уведомление
                    if sent_count > 0:
                        await notify_admin(
                            f"✅ <b>Отправка завершена!</b>\n\n"
                            f"Отправлено: {sent_count} из {max_drafts}\n"
                            f"Ошибок: {error_count}",
                            bot=bot
                        )

                    return sent_count
            finally:
                # Закрываем Bot сессию перед закрытием engine
                await bot.session.close()
                await engine.dispose()

        count = run_async(send_drafts())

        logger.info("send_drafts_to_admin_task_completed", count=count)

        return f"Sent {count} drafts to admin"

    except Exception as exc:
        logger.error("send_drafts_to_admin_task_error", error=str(exc), exc_info=True)

        # Отправляем уведомление об ошибке
        async def send_error():
            from aiogram import Bot
            bot = Bot(token=settings.telegram_bot_token)
            try:
                await notify_admin(
                    f"❌ <b>Ошибка отправки драфтов!</b>\n\n"
                    f"Ошибка: {str(exc)}\n\n"
                    f"Используйте /drafts для ручного просмотра.",
                    bot=bot
                )
            finally:
                await bot.session.close()

        try:
            run_async(send_error())
        except:
            pass

        raise  # Retry если есть лимит retries


@app.task(name="daily_workflow_task")
def daily_workflow_task():
    """
    Полный ежедневный workflow.

    Последовательно запускает:
    1. fetch_news_task
    2. clean_news_task
    3. analyze_articles_task
    4. generate_media_task
    5. send_drafts_to_admin_task (независимо от результата предыдущих)

    Запуск: ежедневно в 09:00 MSK
    """
    from celery import chain, group

    logger.info("daily_workflow_task_started")

    try:
        # Создаем цепочку основных задач
        main_workflow = chain(
            fetch_news_task.si(),
            clean_news_task.si(),
            analyze_articles_task.si(),
            generate_media_task.si(),
        )

        # Запускаем основную цепочку
        result = main_workflow.apply_async()

        # Независимо запускаем отправку драфтов с задержкой 25 минут
        # Это гарантирует что даже если основной workflow упадёт,
        # драфты всё равно будут отправлены если они есть в БД
        send_drafts_to_admin_task.apply_async(countdown=25 * 60)

        logger.info("daily_workflow_task_chain_started",
                   main_workflow_id=result.id,
                   drafts_scheduled=True)

        # Отправляем уведомление о запуске
        async def send_notification():
            from aiogram import Bot
            bot = Bot(token=settings.telegram_bot_token)
            try:
                await notify_admin(
                    "🔄 <b>Ежедневный workflow запущен!</b>\n\n"
                    "Ожидайте завершения через 10-15 минут.\n"
                    "Проверьте новые драфты с помощью /drafts",
                    bot=bot
                )
            finally:
                await bot.session.close()

        run_async(send_notification())

        return f"Daily workflow chain started: {result.id}"

    except Exception as e:
        logger.error("daily_workflow_task_error", error=str(e))

        async def send_error_notification():
            from aiogram import Bot
            bot = Bot(token=settings.telegram_bot_token)
            try:
                await notify_admin(
                    f"❌ <b>Ошибка в ежедневном workflow!</b>\n\n"
                    f"Ошибка: {str(e)}",
                    bot=bot
                )
            finally:
                await bot.session.close()

        run_async(send_error_notification())

        raise


# ====================
# Расписание задач
# ====================

app.conf.beat_schedule = {
    # ОПТИМИЗИРОВАННОЕ РАСПИСАНИЕ: 3 генерации в день с лимитами
    # Утренняя генерация: 09:00 MSK
    'weekday-morning-workflow': {
        'task': 'daily_workflow_task',
        'schedule': crontab(hour=9, minute=0, day_of_week='1-5'),  # Пн-Пт 09:00
    },
    # Дневная генерация: 13:00 MSK
    'weekday-afternoon-workflow': {
        'task': 'daily_workflow_task',
        'schedule': crontab(hour=13, minute=0, day_of_week='1-5'),  # Пн-Пт 13:00
    },
    # Вечерняя генерация: 17:00 MSK
    'weekday-evening-workflow': {
        'task': 'daily_workflow_task',
        'schedule': crontab(hour=17, minute=0, day_of_week='1-5'),  # Пн-Пт 17:00
    },

    # ВЫХОДНЫЕ (Суббота-Воскресенье): 1 итоговая генерация
    # Утренняя генерация: 10:00 MSK
    'weekend-workflow': {
        'task': 'daily_workflow_task',
        'schedule': crontab(hour=10, minute=0, day_of_week='0,6'),  # Сб-Вс 10:00
    },

    # СБОР TELEGRAM МЕТРИК: каждые 6 часов
    'collect-telegram-metrics': {
        'task': 'collect_telegram_metrics_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Каждые 6 часов: 00:00, 06:00, 12:00, 18:00 MSK
    },
}


# ====================
# Сбор Telegram метрик
# ====================

@app.task(name="collect_telegram_metrics_task", max_retries=2, autoretry_for=(Exception,), retry_backoff=300)
def collect_telegram_metrics_task():
    """
    Автоматический сбор метрик из Telegram (views, forwards).
    Запускается каждые 6 часов.

    Returns:
        Dict с результатами сбора
    """
    logger.info("collect_telegram_metrics_task_started")

    async def collect_metrics():
        from app.models.database import get_db, Publication, PersonalPost
        from sqlalchemy import select
        from datetime import datetime, timedelta
        from telethon import TelegramClient
        from app.config import settings

        try:
            # Подключаемся к Telegram через Telethon (MTProto API)
            # Используем ту же сессию что и для сбора новостей
            # Абсолютный путь к session файлу для Celery worker
            session_path = '/app/telegram_bot'
            client = TelegramClient(
                session_path,
                settings.telegram_api_id,
                settings.telegram_api_hash
            )

            # Подключаемся БЕЗ интерактивной авторизации (session уже создан)
            await client.connect()

            # Проверяем авторизацию
            if not await client.is_user_authorized():
                logger.error("telegram_session_not_authorized",
                           session_path=session_path)
                raise Exception("Telegram session not authorized. Run setup_telegram_session.py first.")

            logger.info("telegram_client_connected", session_path=session_path)

            # Получаем публикации за последние 30 дней
            async for db in get_db():
                date_from = datetime.utcnow() - timedelta(days=30)

                result = await db.execute(
                    select(Publication)
                    .where(Publication.published_at >= date_from)
                    .order_by(Publication.published_at.desc())
                )
                publications = result.scalars().all()

                updated_count = 0
                errors_count = 0

                for pub in publications:
                    try:
                        # Получаем информацию о сообщении из Telegram через MTProto
                        # channel_id может быть username или numeric ID
                        message = await client.get_messages(
                            entity=pub.channel_id,
                            ids=pub.message_id
                        )

                        if message:
                            # Обновляем views и forwards
                            old_views = pub.views or 0
                            old_forwards = pub.forwards or 0

                            pub.views = message.views or 0
                            pub.forwards = message.forwards or 0

                            # Логируем только если значения изменились
                            if pub.views != old_views or pub.forwards != old_forwards:
                                logger.info(
                                    "metrics_updated",
                                    pub_id=pub.id,
                                    message_id=pub.message_id,
                                    views=pub.views,
                                    forwards=pub.forwards,
                                    views_delta=pub.views - old_views,
                                    forwards_delta=pub.forwards - old_forwards
                                )
                                updated_count += 1

                    except Exception as e:
                        logger.warning(
                            "collect_metrics_error_single",
                            pub_id=pub.id,
                            message_id=pub.message_id,
                            error=str(e)
                        )
                        errors_count += 1
                        continue

                # Сохраняем изменения для публикаций
                await db.commit()

                logger.info(
                    "publications_metrics_collected",
                    total_publications=len(publications),
                    updated=updated_count,
                    errors=errors_count
                )

                # Собираем метрики для личных постов
                personal_posts_result = await db.execute(
                    select(PersonalPost)
                    .where(
                        PersonalPost.published == True,
                        PersonalPost.telegram_message_id.isnot(None),
                        PersonalPost.published_at >= date_from
                    )
                    .order_by(PersonalPost.published_at.desc())
                )
                personal_posts = personal_posts_result.scalars().all()

                personal_updated_count = 0
                personal_errors_count = 0

                for post in personal_posts:
                    try:
                        # Получаем информацию о сообщении из Telegram
                        message = await client.get_messages(
                            entity=settings.telegram_channel_id,
                            ids=post.telegram_message_id
                        )

                        if message:
                            # Обновляем views и reactions
                            old_views = post.views_count or 0
                            old_reactions = post.reactions_count or 0

                            post.views_count = message.views or 0

                            # Подсчитываем реакции
                            reactions_total = 0
                            if message.reactions and message.reactions.results:
                                for reaction in message.reactions.results:
                                    reactions_total += reaction.count

                            post.reactions_count = reactions_total

                            # Логируем только если значения изменились
                            if post.views_count != old_views or post.reactions_count != old_reactions:
                                logger.info(
                                    "personal_post_metrics_updated",
                                    post_id=post.id,
                                    message_id=post.telegram_message_id,
                                    views=post.views_count,
                                    reactions=post.reactions_count,
                                    views_delta=post.views_count - old_views,
                                    reactions_delta=post.reactions_count - old_reactions
                                )
                                personal_updated_count += 1

                    except Exception as e:
                        logger.warning(
                            "collect_personal_post_metrics_error",
                            post_id=post.id,
                            message_id=post.telegram_message_id,
                            error=str(e)
                        )
                        personal_errors_count += 1
                        continue

                # Сохраняем изменения для личных постов
                await db.commit()

                logger.info(
                    "personal_posts_metrics_collected",
                    total_personal_posts=len(personal_posts),
                    updated=personal_updated_count,
                    errors=personal_errors_count
                )

                # Отключаемся от Telegram
                await client.disconnect()

                logger.info(
                    "collect_telegram_metrics_task_completed",
                    total_publications=len(publications),
                    publications_updated=updated_count,
                    publications_errors=errors_count,
                    total_personal_posts=len(personal_posts),
                    personal_posts_updated=personal_updated_count,
                    personal_posts_errors=personal_errors_count
                )

                return {
                    "status": "success",
                    "publications": {
                        "total": len(publications),
                        "updated": updated_count,
                        "errors": errors_count
                    },
                    "personal_posts": {
                        "total": len(personal_posts),
                        "updated": personal_updated_count,
                        "errors": personal_errors_count
                    }
                }

        except Exception as e:
            logger.error("collect_telegram_metrics_task_error", error=str(e))
            raise

    try:
        result = run_async(collect_metrics())
        return result
    except Exception as e:
        logger.error("collect_telegram_metrics_task_failed", error=str(e))
        raise


# ====================
# Векторизация публикаций
# ====================

@app.task(max_retries=3, autoretry_for=(Exception,), retry_backoff=60)
def vectorize_publication_task(pub_id: int, content: str, draft_id: int):
    """
    Векторизация опубликованного поста в Qdrant.

    Args:
        pub_id: ID публикации
        content: Текст поста
        draft_id: ID драфта
    """
    logger.info("vectorize_publication_task_started", pub_id=pub_id, draft_id=draft_id)

    async def vectorize():
        from app.modules.vector_search import get_vector_search
        from datetime import datetime

        try:
            vector_search = get_vector_search()
            await vector_search.add_publication(
                pub_id=pub_id,
                content=content,
                published_at=datetime.utcnow(),
                reactions={}
            )
            logger.info("vectorize_publication_task_success", pub_id=pub_id, draft_id=draft_id)
            return {"status": "success", "pub_id": pub_id}
        except Exception as e:
            logger.error("vectorize_publication_task_error", pub_id=pub_id, error=str(e))
            raise

    try:
        result = asyncio.run(vectorize())
        return result
    except Exception as e:
        logger.error("vectorize_publication_task_failed", pub_id=pub_id, error=str(e))
        raise


# ====================
# Команды для ручного запуска
# ====================

@app.task(name="manual_fetch")
def manual_fetch():
    """Ручной запуск сбора новостей."""
    return fetch_news_task.delay()


@app.task(name="manual_workflow")
def manual_workflow():
    """Ручной запуск полного workflow."""
    return daily_workflow_task.delay()
