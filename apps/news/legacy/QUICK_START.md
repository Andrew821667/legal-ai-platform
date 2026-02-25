# 🚀 Быстрый запуск Telegram Integration

## ⚡ Автоматическая установка (рекомендуется)

```bash
# Одна команда для полной настройки
./setup_telegram.sh
```

Скрипт автоматически:
- ✅ Создаст/обновит .env с credentials
- ✅ Установит зависимости (telethon)
- ✅ Пересоберёт Docker контейнеры
- ✅ Поможет с авторизацией
- ✅ Перезапустит сервисы

---

## 🔧 Ручная установка (пошагово)

### Шаг 1: Обновить .env

```bash
# Добавить в .env
cat >> .env << 'EOF'

# Telegram Client API
TELEGRAM_API_ID=34617695
TELEGRAM_API_HASH=e95e6e190f5efcff98001a490acea1c1
TELEGRAM_SESSION_NAME=telegram_bot
TELEGRAM_CHANNELS=@ai_newz,@mlnews,@legaltechnews,@rb_tech,@tass_tech,@habr
TELEGRAM_FETCH_LIMIT=50
TELEGRAM_FETCH_ENABLED=true
EOF
```

### Шаг 2: Установить зависимости

```bash
# Вариант A: Docker (рекомендуется)
docker compose build --no-cache app celery_worker bot

# Вариант B: Локально
pip install telethon==1.34.0
```

### Шаг 3: Авторизация Telegram

```bash
# Интерактивный скрипт
python setup_telegram_session.py
```

### Шаг 4: Перезапустить сервисы

```bash
docker compose restart celery_worker bot app
```

### Шаг 5: Проверить статус

```bash
docker compose ps
```

---

## 🧪 Тестирование

### Запустить сбор вручную

```bash
# В Telegram боте отправьте:
/fetch
```

### Проверить логи

```bash
# Все логи Telegram
docker compose logs -f celery_worker | grep telegram

# Только ошибки
docker compose logs celery_worker | grep -i error | grep telegram

# Статистика сбора
docker compose logs celery_worker | grep "telegram_fetch_all_complete"
```

### Проверить файл сессии

```bash
# Должен существовать после авторизации
ls -la telegram_bot.session*
```

### Проверить конфигурацию

```bash
# Показать все Telegram параметры
grep TELEGRAM .env

# Показать список каналов
grep TELEGRAM_CHANNELS .env | cut -d'=' -f2
```

---

## 🔍 Диагностика

### Проблема: "Telegram session not authorized"

```bash
# Решение: Запустить авторизацию
python setup_telegram_session.py
```

### Проблема: "No module named 'telethon'"

```bash
# Решение: Установить зависимость
pip install telethon==1.34.0

# ИЛИ пересобрать Docker
docker compose build --no-cache app celery_worker bot
```

### Проблема: "Telegram channels not configured"

```bash
# Решение: Добавить каналы в .env
echo "TELEGRAM_CHANNELS=@ai_newz,@mlnews,@legaltechnews" >> .env
docker compose restart celery_worker
```

### Проблема: Нет новостей из Telegram

```bash
# Проверить 1: Включен ли Telegram fetch
grep TELEGRAM_FETCH_ENABLED .env
# Должно быть: TELEGRAM_FETCH_ENABLED=true

# Проверить 2: Есть ли API credentials
grep TELEGRAM_API_ID .env
grep TELEGRAM_API_HASH .env

# Проверить 3: Есть ли session файл
ls telegram_bot.session

# Проверить 4: Логи сбора
docker compose logs celery_worker | grep "fetching_telegram_channel"
```

---

## 📊 Мониторинг

### Живые логи сбора

```bash
# Следить за процессом сбора в реальном времени
docker compose logs -f celery_worker | grep -E "(fetching_telegram|telegram_message_fetched|telegram_channel_fetch_complete)"
```

### Статистика последнего сбора

```bash
# Посмотреть последнюю статистику
docker compose logs celery_worker | grep "telegram_fetch_all_complete" | tail -1
```

### Детальная статистика по каналам

```bash
# Посмотреть сколько новостей с каждого канала
docker compose logs celery_worker | grep "telegram_detailed_stats" | tail -1
```

### Проверить фильтрацию

```bash
# Посмотреть отфильтрованные сообщения
docker compose logs celery_worker | grep "telegram_message_filtered" | tail -20
```

---

## ⚙️ Настройка каналов

### Добавить каналы

```bash
# Отредактировать список каналов в .env
nano .env
# Найти: TELEGRAM_CHANNELS=...
# Добавить новые каналы через запятую

# Перезапустить
docker compose restart celery_worker
```

### Рекомендуемые каналы

```bash
# AI/ML новости
@ai_newz
@mlnews
@deeplearning_ru

# LegalTech
@legaltechnews
@legaltech_russia

# Бизнес + Tech
@rb_tech
@tass_tech
@vcru
@habr

# Настроить все сразу:
sed -i 's/^TELEGRAM_CHANNELS=.*/TELEGRAM_CHANNELS=@ai_newz,@mlnews,@deeplearning_ru,@legaltechnews,@legaltech_russia,@rb_tech,@tass_tech,@vcru,@habr/' .env
docker compose restart celery_worker
```

### Изменить лимит сообщений

```bash
# Больше сообщений с каждого канала
sed -i 's/^TELEGRAM_FETCH_LIMIT=.*/TELEGRAM_FETCH_LIMIT=100/' .env
docker compose restart celery_worker

# Меньше (быстрее, но меньше новостей)
sed -i 's/^TELEGRAM_FETCH_LIMIT=.*/TELEGRAM_FETCH_LIMIT=20/' .env
docker compose restart celery_worker
```

---

## 🎯 Быстрые команды

### Пересоздать все с нуля

```bash
# Полный сброс и настройка
rm -f telegram_bot.session*
./setup_telegram.sh
```

### Только перезапуск сервисов

```bash
docker compose restart celery_worker bot app
```

### Только проверка логов

```bash
docker compose logs --tail=100 celery_worker | grep telegram
```

### Только проверка статуса

```bash
docker compose ps | grep -E "(celery_worker|bot|app)"
```

### Ручной тест сбора (без бота)

```bash
# Запустить Celery task вручную
docker compose exec celery_worker celery -A app.tasks.celery_tasks call app.tasks.celery_tasks.fetch_news_task
```

---

## 📖 Дополнительная документация

- **TELEGRAM_SETUP.md** - Подробное руководство по настройке
- **TELEGRAM_INTEGRATION_SUMMARY.md** - Полная техническая сводка
- **current.md** - Общая документация проекта

---

## ✅ Checklist готовности

Перед запуском убедитесь:

```bash
# 1. .env содержит Telegram credentials
grep -E "TELEGRAM_API_(ID|HASH)" .env

# 2. Каналы настроены
grep TELEGRAM_CHANNELS .env

# 3. Telegram fetch включен
grep "TELEGRAM_FETCH_ENABLED=true" .env

# 4. Сессия авторизована
ls telegram_bot.session

# 5. Docker контейнеры запущены
docker compose ps | grep -E "Up.*celery_worker"

# 6. Telethon установлен
docker compose exec celery_worker python -c "import telethon; print('✅ OK')"
```

Если все команды прошли успешно - система готова! 🎉

---

## 🚨 Экстренное восстановление

Если что-то сломалось:

```bash
# 1. Остановить все
docker compose down

# 2. Очистить session
rm -f telegram_bot.session*

# 3. Пересобрать контейнеры
docker compose build --no-cache

# 4. Запустить заново
docker compose up -d

# 5. Авторизоваться
python setup_telegram_session.py

# 6. Проверить
docker compose logs -f celery_worker | grep telegram
```
