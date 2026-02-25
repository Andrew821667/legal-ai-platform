#!/usr/bin/env python3
"""
Скрипт проверки статуса workflow сбора новостей.

Использование:
    docker compose exec app python check_workflow_status.py
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sqlalchemy import select, func, desc
    from app.models.database import get_db
    from app.models.models import RawArticle, Draft, Publication
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print()
    print("Этот скрипт должен запускаться внутри Docker контейнера:")
    print("  docker compose exec app python check_workflow_status.py")
    sys.exit(1)


async def check_workflow_status():
    """Проверить статус workflow."""
    print("=" * 80)
    print("🔍 ПРОВЕРКА СТАТУСА WORKFLOW")
    print("=" * 80)
    print()

    async for db in get_db():
        # 1. Проверка raw_articles за последние 2 дня
        two_days_ago = datetime.utcnow() - timedelta(days=2)

        result = await db.execute(
            select(func.count(RawArticle.id))
            .where(RawArticle.fetched_at >= two_days_ago)
        )
        raw_count = result.scalar()

        print(f"📰 Raw Articles (последние 2 дня): {raw_count}")

        # Последняя статья
        result = await db.execute(
            select(RawArticle.fetched_at, RawArticle.source, RawArticle.title)
            .order_by(desc(RawArticle.fetched_at))
            .limit(1)
        )
        last_raw = result.first()
        if last_raw:
            print(f"   Последняя: {last_raw.fetched_at} | {last_raw.source}")
            print(f"   Заголовок: {last_raw.title[:80]}...")
        else:
            print("   ❌ НЕТ СТАТЕЙ!")
        print()

        # 2. Проверка drafts за последние 2 дня
        result = await db.execute(
            select(func.count(Draft.id))
            .where(Draft.created_at >= two_days_ago)
        )
        draft_count = result.scalar()

        print(f"📝 Drafts (последние 2 дня): {draft_count}")

        # Последний драфт
        result = await db.execute(
            select(Draft.created_at, Draft.status, Draft.title)
            .order_by(desc(Draft.created_at))
            .limit(1)
        )
        last_draft = result.first()
        if last_draft:
            print(f"   Последний: {last_draft.created_at} | {last_draft.status}")
            print(f"   Заголовок: {last_draft.title[:80]}...")
        else:
            print("   ❌ НЕТ ДРАФТОВ!")
        print()

        # 3. Проверка publications за последние 2 дня
        result = await db.execute(
            select(func.count(Publication.id))
            .where(Publication.published_at >= two_days_ago)
        )
        pub_count = result.scalar()

        print(f"📢 Publications (последние 2 дня): {pub_count}")

        # Последняя публикация
        result = await db.execute(
            select(Publication.published_at, Publication.title)
            .order_by(desc(Publication.published_at))
            .limit(1)
        )
        last_pub = result.first()
        if last_pub:
            print(f"   Последняя: {last_pub.published_at}")
            print(f"   Заголовок: {last_pub.title[:80]}...")
        else:
            print("   ℹ️  Нет публикаций")
        print()

        # 4. Анализ проблемы
        print("=" * 80)
        print("📊 АНАЛИЗ")
        print("=" * 80)

        if raw_count == 0:
            print("❌ ПРОБЛЕМА: Нет raw_articles за последние 2 дня")
            print("   Возможные причины:")
            print("   1. Celery Beat не запущен")
            print("   2. Celery Worker не запущен")
            print("   3. fetch_news_task падает с ошибкой")
            print("   4. Нет доступа к источникам новостей")
            print()
            print("   🔧 Решение:")
            print("   1. Проверьте: docker compose ps")
            print("   2. Проверьте логи: docker compose logs celery_worker")
            print("   3. Запустите вручную: docker compose exec app python -c 'from app.tasks.celery_tasks import fetch_news_task; fetch_news_task()'")
        elif draft_count == 0:
            print("❌ ПРОБЛЕМА: Raw articles есть, но нет drafts")
            print("   Возможные причины:")
            print("   1. analyze_articles_task падает с ошибкой")
            print("   2. Все статьи отфильтрованы (низкий score)")
            print("   3. Проблема с AI API (OpenAI)")
            print()
            print("   🔧 Решение:")
            print("   1. Проверьте логи: docker compose logs celery_worker | grep analyze")
            print("   2. Проверьте настройки фильтрации: min_score, min_content_length")
            print("   3. Проверьте баланс OpenAI API")
        else:
            print("✅ СТАТУС: Данные собираются нормально")
            print(f"   Raw Articles: {raw_count}")
            print(f"   Drafts: {draft_count}")
            print(f"   Publications: {pub_count}")
        print()

        # 5. Текущее время и следующий запуск
        now = datetime.utcnow()
        print("=" * 80)
        print("⏰ РАСПИСАНИЕ")
        print("=" * 80)
        print(f"Текущее время UTC: {now}")
        print()
        print("Workflow запускается:")
        print("  Будни (Пн-Пт): 09:00, 13:00, 17:00 MSK (06:00, 10:00, 14:00 UTC)")
        print("  Выходные (Сб-Вс): 10:00 MSK (07:00 UTC)")
        print()

        # Вычисляем следующий запуск
        hour_utc = now.hour
        day_of_week = now.weekday()  # 0=Mon, 6=Sun

        if day_of_week < 5:  # Weekday
            next_runs = [6, 10, 14]
            next_run = None
            for h in next_runs:
                if hour_utc < h:
                    next_run = h
                    break
            if next_run:
                print(f"Следующий запуск: сегодня в {next_run:02d}:00 UTC")
            else:
                print(f"Следующий запуск: завтра в 06:00 UTC")
        else:  # Weekend
            if hour_utc < 7:
                print(f"Следующий запуск: сегодня в 07:00 UTC")
            else:
                print(f"Следующий запуск: завтра в 07:00 UTC (если выходной)")
        print()

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(check_workflow_status())
