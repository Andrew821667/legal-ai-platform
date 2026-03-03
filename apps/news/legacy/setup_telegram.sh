#!/bin/bash
# Автоматизированный запуск Telegram Channel API Integration
set -e

echo "========================================"
echo "🚀 Telegram Channel API - Автоматическая настройка"
echo "========================================"
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для вывода успеха
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Функция для вывода предупреждения
warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Функция для вывода ошибки
error() {
    echo -e "${RED}❌ $1${NC}"
}

# Шаг 1: Проверка .env файла
echo "📋 Шаг 1: Проверка конфигурации"
if [ ! -f .env ]; then
    error ".env файл не найден"
    echo "Создаю из .env.example..."
    cp .env.example .env
    success ".env файл создан"
else
    success ".env файл существует"
fi

# Шаг 2: Обновление .env с Telegram credentials
echo ""
echo "📝 Шаг 2: Обновление Telegram credentials"

# Проверяем есть ли уже credentials
if grep -q "^TELEGRAM_API_ID=34617695" .env 2>/dev/null; then
    success "Telegram credentials уже настроены"
else
    warning "Добавляю Telegram credentials в .env..."

    # Добавляем или обновляем credentials
    if grep -q "^TELEGRAM_API_ID=" .env; then
        sed -i 's/^TELEGRAM_API_ID=.*/TELEGRAM_API_ID=34617695/' .env
        sed -i 's/^TELEGRAM_API_HASH=.*/TELEGRAM_API_HASH=e95e6e190f5efcff98001a490acea1c1/' .env
    else
        cat >> .env << 'EOF'

# Telegram Client API (для сбора новостей из каналов)
TELEGRAM_API_ID=34617695
TELEGRAM_API_HASH=e95e6e190f5efcff98001a490acea1c1
TELEGRAM_SESSION_NAME=telegram_bot
TELEGRAM_CHANNELS=@ai_newz,@mlnews,@legaltechnews,@rb_tech,@tass_tech,@habr
TELEGRAM_FETCH_LIMIT=50
TELEGRAM_FETCH_ENABLED=true
EOF
    fi
    success "Telegram credentials добавлены в .env"
fi

# Проверка других необходимых параметров
if ! grep -q "^TELEGRAM_CHANNELS=" .env; then
    echo "TELEGRAM_CHANNELS=@ai_newz,@mlnews,@legaltechnews,@rb_tech,@tass_tech,@habr" >> .env
fi
if ! grep -q "^TELEGRAM_FETCH_LIMIT=" .env; then
    echo "TELEGRAM_FETCH_LIMIT=50" >> .env
fi
if ! grep -q "^TELEGRAM_FETCH_ENABLED=" .env; then
    echo "TELEGRAM_FETCH_ENABLED=true" >> .env
fi
if ! grep -q "^TELEGRAM_SESSION_NAME=" .env; then
    echo "TELEGRAM_SESSION_NAME=telegram_bot" >> .env
fi

# Шаг 3: Установка зависимостей
echo ""
echo "📦 Шаг 3: Установка зависимостей"
if command -v docker &> /dev/null; then
    warning "Пересборка Docker контейнеров..."
    docker compose build --no-cache app celery_worker bot 2>&1 | tail -10
    success "Docker контейнеры пересобраны"
else
    warning "Docker не найден, устанавливаю через pip..."
    pip install -q telethon==1.34.0
    success "telethon установлен"
fi

# Шаг 4: Проверка существующей сессии
echo ""
echo "🔐 Шаг 4: Проверка авторизации Telegram"
if [ -f "telegram_bot.session" ]; then
    success "Файл сессии найден: telegram_bot.session"
    echo "   Авторизация уже выполнена, пропускаю..."
else
    warning "Файл сессии не найден"
    echo ""
    echo "Нужна первоначальная авторизация Telegram Client API"
    echo ""
    echo "Выберите метод авторизации:"
    echo "  1. Запустить интерактивный вход (QR или номер телефона)"
    echo "  2. Пропустить (настроить позже)"
    echo ""
    read -p "Ваш выбор (1/2): " auth_choice

    case $auth_choice in
        1)
            warning "Запускаю интерактивный скрипт авторизации..."
            python3 setup_telegram_session.py
            ;;
        2)
            warning "Авторизация пропущена"
            echo "   Запустите позже: python setup_telegram_session.py"
            ;;
        *)
            warning "Неверный выбор, пропускаю авторизацию"
            ;;
    esac
fi

# Шаг 5: Перезапуск контейнеров
echo ""
echo "🔄 Шаг 5: Перезапуск сервисов"
if command -v docker &> /dev/null; then
    warning "Перезапуск Docker контейнеров..."
    docker compose restart celery_worker bot app
    success "Контейнеры перезапущены"

    echo ""
    echo "📊 Статус контейнеров:"
    docker compose ps | grep -E "(celery_worker|bot|app)"
else
    warning "Docker не найден, пропускаю перезапуск"
fi

# Шаг 6: Инструкции по тестированию
echo ""
echo "========================================"
echo "✅ Настройка завершена!"
echo "========================================"
echo ""
echo "📋 Следующие шаги:"
echo ""
echo "1. Проверьте конфигурацию:"
echo "   cat .env | grep TELEGRAM"
echo ""
echo "2. Проверьте файл сессии:"
echo "   ls -la telegram_bot.session"
echo ""
echo "3. Протестируйте сбор новостей:"
echo "   - Откройте Telegram бота"
echo "   - Отправьте команду: /fetch"
echo "   - Дождитесь статистики сбора"
echo ""
echo "4. Проверьте логи:"
echo "   docker compose logs -f celery_worker | grep telegram"
echo ""
echo "5. Проверьте список каналов в .env:"
echo "   grep TELEGRAM_CHANNELS .env"
echo ""
echo "📖 Документация:"
echo "   - TELEGRAM_SETUP.md - подробное руководство"
echo "   - TELEGRAM_INTEGRATION_SUMMARY.md - полная сводка"
echo ""
echo "🎯 Рекомендуемые каналы для мониторинга:"
echo "   @ai_newz, @mlnews, @legaltechnews"
echo "   @rb_tech, @tass_tech, @vcru, @habr"
echo ""
echo "========================================"
