# 🔍 Диагностика проблем с Workflow сбора новостей

## Симптом: Нет новых драфтов уже 2 дня

### Шаг 1: Проверка статуса контейнеров

```bash
# Проверьте, что все контейнеры запущены
docker compose ps

# Должны быть запущены:
# - bot (Telegram бот)
# - app (FastAPI)
# - celery_worker (обработка задач)
# - celery_beat (планировщик задач) ⚠️ ВАЖНО!
# - db (PostgreSQL)
# - redis (брокер сообщений)
```

**Если celery_beat не запущен:**
```bash
docker compose up -d celery_beat
```

### Шаг 2: Автоматическая диагностика

```bash
# Запустите скрипт диагностики
docker compose exec app python check_workflow_status.py
```

Скрипт покажет:
- ✅ Сколько raw_articles собрано за последние 2 дня
- ✅ Сколько drafts создано
- ✅ Когда была последняя активность
- ✅ Расписание следующих запусков
- ✅ Диагноз проблемы и рекомендации

### Шаг 3: Проверка логов

```bash
# Логи celery_worker (обработка задач)
docker compose logs celery_worker --tail=100 -f

# Логи celery_beat (планировщик)
docker compose logs celery_beat --tail=50 -f

# Поиск ошибок
docker compose logs celery_worker | grep -i "error\|exception\|failed"
```

### Шаг 4: Ручной запуск workflow

Если автоматический запуск не работает, запустите вручную:

```bash
# Войдите в контейнер
docker compose exec app bash

# Запустите Python и выполните
python3 << 'EOF'
from app.tasks.celery_tasks import daily_workflow_task
result = daily_workflow_task.delay()
print(f"Task ID: {result.id}")
EOF

# Выход из контейнера
exit
```

### Шаг 5: Проверка настроек

```bash
# Проверьте настройки фильтрации в БД
docker compose exec db psql -U postgres legal_ai_news -c "
SELECT key, value FROM system_settings
WHERE key LIKE 'filtering%' OR key LIKE 'fetcher%';
"
```

Убедитесь что:
- `filtering.min_score` не слишком высокий (рекомендуется 0.6)
- `filtering.min_content_length` не слишком большой (рекомендуется 300)
- `fetcher.max_articles_per_source` достаточно большой (рекомендуется 300)

---

## Возможные причины и решения

### ❌ Причина 1: Celery Beat не запущен

**Симптомы:** Нет raw_articles, нет драфтов, нет активности

**Решение:**
```bash
docker compose up -d celery_beat
docker compose logs celery_beat -f
```

---

### ❌ Причина 2: Ошибка в fetch_news_task

**Симптомы:** Нет raw_articles

**Проверка:**
```bash
docker compose logs celery_worker | grep "fetch_news"
```

**Возможные ошибки:**
- `ConnectionError` - нет доступа к источникам новостей
- `RateLimitError` - превышен лимит запросов
- `DatabaseError` - проблема с БД

**Решение:**
```bash
# Проверьте доступность источников
docker compose exec app python3 << 'EOF'
import requests
sources = [
    "https://pravo.ru/news/",
    "https://zakon.ru/News",
    "https://www.garant.ru/news/",
]
for url in sources:
    try:
        r = requests.get(url, timeout=10)
        print(f"✅ {url}: {r.status_code}")
    except Exception as e:
        print(f"❌ {url}: {e}")
EOF
```

---

### ❌ Причина 3: Все статьи отфильтрованы

**Симптомы:** Raw articles есть, но нет drafts

**Проверка:**
```bash
# Проверьте scored_at и quality_score в raw_articles
docker compose exec db psql -U postgres legal_ai_news -c "
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN quality_score >= 0.6 THEN 1 END) as high_quality,
    AVG(quality_score) as avg_score
FROM raw_articles
WHERE fetched_at >= NOW() - INTERVAL '2 days';
"
```

**Решение:** Понизить `filtering.min_score` в настройках бота (`/settings`)

---

### ❌ Причина 4: Проблема с OpenAI API

**Симптомы:** Raw articles есть, но нет drafts. В логах ошибки OpenAI

**Проверка:**
```bash
docker compose logs celery_worker | grep -i "openai\|api_error"
```

**Возможные ошибки:**
- `RateLimitError` - превышен лимит API
- `AuthenticationError` - неверный API ключ
- `InsufficientQuotaError` - закончились деньги на аккаунте

**Решение:**
1. Проверьте баланс: https://platform.openai.com/account/usage
2. Проверьте лимиты: https://platform.openai.com/account/limits
3. Обновите API ключ в `.env`:
```bash
nano .env
# Обновите OPENAI_API_KEY
docker compose restart app celery_worker
```

---

### ❌ Причина 5: Ошибка в analyze_articles_task

**Симптомы:** Raw articles есть, но нет drafts

**Проверка:**
```bash
docker compose logs celery_worker | grep "analyze_articles"
```

**Решение:** Посмотрите полный traceback ошибки и исправьте код

---

## Расписание workflow

Workflow запускается автоматически:

### Будни (Понедельник-Пятница):
- 09:00 MSK (06:00 UTC) - Утренняя генерация
- 13:00 MSK (10:00 UTC) - Дневная генерация
- 17:00 MSK (14:00 UTC) - Вечерняя генерация

### Выходные (Суббота-Воскресенье):
- 10:00 MSK (07:00 UTC) - Итоговая генерация

### Этапы workflow:
1. `fetch_news_task` - Сбор статей из источников (5-10 мин)
2. `clean_news_task` - Очистка дубликатов и старых статей (1-2 мин)
3. `analyze_articles_task` - AI анализ и оценка качества (5-15 мин)
4. `generate_media_task` - Генерация изображений DALL-E (5-10 мин)
5. `send_drafts_to_admin_task` - Отправка драфтов админу (1 мин)

**Общее время:** 15-40 минут

---

## Мониторинг в реальном времени

```bash
# Следите за выполнением задач
watch -n 5 'docker compose exec db psql -U postgres legal_ai_news -c "SELECT COUNT(*) FROM raw_articles WHERE fetched_at >= NOW() - INTERVAL '\''1 hour'\'';"'

# Следите за драфтами
watch -n 5 'docker compose exec db psql -U postgres legal_ai_news -c "SELECT status, COUNT(*) FROM post_drafts GROUP BY status;"'
```

---

## Экстренное восстановление

Если ничего не помогло:

```bash
# 1. Остановите все
docker compose down

# 2. Очистите логи Redis (если накопились мусорные задачи)
docker compose up -d redis
docker compose exec redis redis-cli FLUSHALL

# 3. Запустите заново
docker compose up -d

# 4. Проверьте статус
docker compose ps

# 5. Запустите workflow вручную
docker compose exec app python3 -c "from app.tasks.celery_tasks import daily_workflow_task; daily_workflow_task.delay()"

# 6. Следите за логами
docker compose logs -f celery_worker celery_beat
```

---

## Полезные команды

```bash
# Проверить, что celery видит задачи
docker compose exec celery_worker celery -A app.tasks.celery_tasks inspect active

# Проверить расписание
docker compose exec celery_beat celery -A app.tasks.celery_tasks inspect scheduled

# Очистить очередь задач
docker compose exec redis redis-cli FLUSHALL

# Перезапустить только celery
docker compose restart celery_worker celery_beat
```

---

## Контакты

Если проблема не решается, сохраните логи и свяжитесь с разработчиком:

```bash
# Сохраните логи за последние 1000 строк
docker compose logs celery_worker --tail=1000 > celery_worker.log
docker compose logs celery_beat --tail=200 > celery_beat.log
docker compose logs app --tail=500 > app.log

# Отправьте файлы разработчику
```
