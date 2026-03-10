# AI-News Aggregator для LegalTech

> ⚠️ Этот README относится к историческому standalone-контуру.
> Для актуального запуска в монорепозитории используйте корневой README (`/README.md`) и runbook (`/docs/runbook.md`).

Полуавтоматизированный программный комплекс для ежедневного сбора, анализа и публикации новостей о внедрении ИИ в юриспруденцию и бизнес с обязательной модерацией.

## 📋 Обзор

**Целевая аудитория:** Юристы, руководители юрдепартаментов, IT-специалисты в праве.

**Ключевая ценность:**
- Экономия времени (автоматический сбор и первичный анализ)
- Безопасность (модерация перед публикацией)
- Профессионализм (юридический контекст с проверкой)

**⚠️ ВАЖНО:** Система генерирует ДРАФТЫ, финальная публикация — после одобрения человеком.

## 🏗️ Архитектура

### Модули системы

1. **Сборщик (Fetcher)** - Легальный сбор контента из проверенных источников
2. **Фильтр (Cleaner)** - Умная очистка с ML-классификацией
3. **AI Core** - Интеллектуальный анализ с проверкой фактов
4. **Media Factory** - Генерация обложек и аудио контента
5. **Publisher** - Модератор и публикатор в Telegram
6. **Analytics** - Сбор метрик и обучение системы

### Технический стек

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy
- **Database:** PostgreSQL 15+
- **Cache/Queue:** Redis 7+, Celery 5.3+
- **AI/ML:** OpenAI API (GPT-4o-mini, GPT-4o, TTS-1), Transformers
- **Telegram:** Aiogram 3.x
- **Infrastructure:** Docker, Docker Compose

## 🚀 Быстрый старт

### Предварительные требования

- Docker и Docker Compose
- OpenAI API ключ
- Telegram Bot Token (от @BotFather)
- Telegram Channel

### 1. Клонирование репозитория

\`\`\`bash
git clone https://github.com/Andrew821667/Telegram_channel_auto.git
cd Telegram_channel_auto
\`\`\`

### 2. Настройка переменных окружения

\`\`\`bash
# Копируем пример конфигурации
cp .env.example .env

# Редактируем .env и заполняем необходимые значения
nano .env
\`\`\`

**Обязательные переменные:**

\`\`\`env
# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key-here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ADMIN_ID=your_telegram_user_id
TELEGRAM_CHANNEL_ID=@your_channel_username

# PostgreSQL (измените пароли!)
POSTGRES_PASSWORD=your_strong_password
REDIS_PASSWORD=your_redis_password
\`\`\`

### 3. Запуск с Docker Compose

\`\`\`bash
# Сборка и запуск всех сервисов
docker-compose up -d

# Проверка логов
docker-compose logs -f

# Проверка статуса сервисов
docker-compose ps
\`\`\`

## 📦 Структура проекта

См. детальную структуру в [current.md](current.md)

## 🔧 Разработка

### Локальная разработка

\`\`\`bash
# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск приложения
python -m app.main
\`\`\`

### Запуск тестов

\`\`\`bash
pytest --cov=app tests/
\`\`\`

## 📊 Мониторинг

\`\`\`bash
# Логи всех сервисов
docker-compose logs -f

# Healthcheck
curl http://localhost:8000/health
\`\`\`

## 🔐 Безопасность

1. **НЕ коммитьте .env файл** с реальными ключами
2. **Измените пароли БД** в production
3. **Используйте HTTPS** для production деплоя

## 📅 Рабочий процесс

### Ежедневный цикл (09:00 MSK)
1. Сбор новостей
2. Фильтрация и анализ
3. Генерация драфтов
4. Модерация администратором
5. Публикация

## 📚 Документация

- **[current.md](current.md)** - ⚠️ ОБЯЗАТЕЛЬНО читать при возобновлении работы!
- Полное ТЗ - см. начало проекта

## 📈 Roadmap

### Phase 1: MVP (В разработке)
- [x] Базовая инфраструктура
- [ ] Fetcher модуль
- [ ] AI генерация
- [ ] Telegram бот
- [ ] Публикация

### Phase 2-4: См. current.md

## 👨‍💻 Автор

Andrew821667

---

**ВАЖНО:** Перед началом работы после перерыва обязательно прочитайте [current.md](current.md)!
