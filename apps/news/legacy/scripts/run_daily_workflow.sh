#!/bin/bash

# Скрипт для запуска ежедневного workflow
# Использование: ./run_daily_workflow.sh

set -e

# Директория проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Логирование
LOG_FILE="$PROJECT_DIR/logs/cron_workflow_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$PROJECT_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily workflow..." | tee -a "$LOG_FILE"

# 1. Запускаем celery worker (если не запущен)
if ! docker compose -f docker-compose.production.yml ps celery_worker | grep -q "Up"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting celery worker..." | tee -a "$LOG_FILE"
    docker compose -f docker-compose.production.yml up -d celery_worker
    sleep 10  # Даем время на запуск
fi

# 2. Запускаем workflow task
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Executing daily_workflow_task..." | tee -a "$LOG_FILE"
docker compose -f docker-compose.production.yml exec -T celery_worker \
    celery -A app.tasks.celery_tasks call app.tasks.celery_tasks.daily_workflow_task \
    >> "$LOG_FILE" 2>&1

# 3. Ждем завершения (максимум 30 минут)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for workflow completion (max 30 min)..." | tee -a "$LOG_FILE"
TIMEOUT=1800  # 30 minutes
ELAPSED=0
INTERVAL=10

while [ $ELAPSED -lt $TIMEOUT ]; do
    # Проверяем что worker еще работает
    if ! docker compose -f docker-compose.production.yml ps celery_worker | grep -q "Up"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Worker stopped unexpectedly" | tee -a "$LOG_FILE"
        break
    fi

    # Проверяем активные задачи
    ACTIVE_TASKS=$(docker compose -f docker-compose.production.yml exec -T celery_worker \
        celery -A app.tasks.celery_tasks inspect active 2>/dev/null | grep -c "fetch_news_task\|clean_news_task\|analyze_articles_task\|generate_media_task\|send_drafts_to_admin_task" || true)

    if [ "$ACTIVE_TASKS" -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] All tasks completed" | tee -a "$LOG_FILE"
        break
    fi

    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

# 4. Останавливаем worker для освобождения памяти
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Stopping celery worker to free memory..." | tee -a "$LOG_FILE"
docker compose -f docker-compose.production.yml stop celery_worker

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily workflow completed" | tee -a "$LOG_FILE"

# 5. Очистка старых логов (старше 7 дней)
find "$PROJECT_DIR/logs" -name "cron_workflow_*.log" -mtime +7 -delete

exit 0
