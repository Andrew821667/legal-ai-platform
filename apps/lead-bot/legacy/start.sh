#!/bin/bash

# Legal AI Telegram Bot - Start Script
# Скрипт для локального запуска бота

# Определение директории скрипта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$SCRIPT_DIR"

echo "🤖 Starting Legal AI Telegram Bot..."
echo "📁 Working directory: $SCRIPT_DIR"

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "   Please create .env file from .env.example"
    echo "   cp .env.example .env"
    echo "   Then edit it with your API keys"
    exit 1
fi

# Проверка наличия виртуального окружения
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv

    echo "📚 Installing dependencies..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "✅ Virtual environment found"
    source venv/bin/activate
fi

# Создание директорий если их нет
mkdir -p data logs

# Проверка наличия базы данных
if [ ! -f "data/bot.db" ]; then
    echo "💾 Initializing database..."
    python database.py
fi

echo ""
echo "🚀 Starting bot..."
echo "   Press Ctrl+C to stop"
echo ""

# Запуск бота
python bot.py
