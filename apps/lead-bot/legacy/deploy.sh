#!/bin/bash
set -e

echo "🚀 Starting deployment..."

cd /opt/legal-ai-bot

# Получаем обновления
git pull origin main

# Активируем виртуальное окружение и обновляем зависимости
source venv/bin/activate
pip install -r requirements.txt

# Перезапускаем бота через systemd
systemctl restart telegram-bot

echo "✅ Deployment completed successfully!"
echo "📅 $(date)" >> /var/log/deploy.log

