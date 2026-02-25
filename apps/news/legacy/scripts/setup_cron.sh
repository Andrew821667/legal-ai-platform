#!/bin/bash

# Скрипт для настройки cron jobs для автоматического запуска workflow
# Запускает сбор новостей 3 раза в день: 09:00, 14:00, 18:00 MSK

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Setting up cron jobs for Legal AI News Bot..."
echo "Schedule: 09:00, 14:00, 18:00 MSK (3 times per day)"
echo ""

# Делаем скрипт исполняемым
chmod +x "$PROJECT_DIR/scripts/run_daily_workflow.sh"

# MSK = UTC+3
# 09:00 MSK = 06:00 UTC
# 14:00 MSK = 11:00 UTC
# 18:00 MSK = 15:00 UTC

CRON_JOBS="
# Legal AI News Bot - Daily Workflow (3 times per day)
0 6 * * * $PROJECT_DIR/scripts/run_daily_workflow.sh  # 09:00 MSK - Morning
0 11 * * * $PROJECT_DIR/scripts/run_daily_workflow.sh # 14:00 MSK - Afternoon
0 15 * * * $PROJECT_DIR/scripts/run_daily_workflow.sh # 18:00 MSK - Evening
"

# Проверяем существующий crontab
if crontab -l >/dev/null 2>&1; then
    echo "Found existing crontab"

    # Проверяем наличие наших задач
    if crontab -l | grep -q "Legal AI News Bot"; then
        echo "⚠️  Cron jobs already exist!"
        echo ""
        echo "Current cron jobs:"
        crontab -l | grep -A 3 "Legal AI News Bot"
        echo ""
        read -p "Do you want to replace them? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Cancelled"
            exit 0
        fi

        # Удаляем старые задачи
        crontab -l | grep -v "Legal AI News Bot" | grep -v "$PROJECT_DIR/scripts/run_daily_workflow.sh" | crontab -
    fi
fi

# Добавляем новые задачи
(crontab -l 2>/dev/null; echo "$CRON_JOBS") | crontab -

echo "✅ Cron jobs installed successfully!"
echo ""
echo "Installed schedule:"
crontab -l | grep -A 3 "Legal AI News Bot"
echo ""
echo "Logs will be saved to: $PROJECT_DIR/logs/cron_workflow_*.log"
echo ""
echo "To view cron jobs: crontab -l"
echo "To remove cron jobs: crontab -e"
echo "To test manually: $PROJECT_DIR/scripts/run_daily_workflow.sh"
