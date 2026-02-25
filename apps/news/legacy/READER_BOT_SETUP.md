# Reader Bot Setup Guide

## 📋 Overview

Reader Bot - персонализированный бот для читателей канала Legal AI News. Позволяет:

- 🎯 Онбординг с настройкой интересов
- 📰 Персональная лента новостей
- 🔍 Поиск по архиву
- 🔖 Сохранение статей
- 👍 Фидбек (полезно/не интересно)
- 📬 Автоматические дайджесты

---

## 🚀 Quick Start

### Шаг 1: Создать бота в BotFather

1. Откройте Telegram → @BotFather
2. Отправьте: `/newbot`
3. Введите название: `Legal AI News Reader Bot`
4. Введите username: `@legal_ai_news_reader_bot`
5. Скопируйте токен

### Шаг 2: Добавить токен в .env

```bash
# Откройте .env
nano .env

# Добавьте строку:
READER_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

### Шаг 3: Применить миграцию БД

```bash
# Применить миграцию для создания таблиц
docker compose exec postgres psql -U legal_user -d legal_ai_news -f /migrations/018_add_reader_tables.sql

# Или вручную:
cat migrations/018_add_reader_tables.sql | \
  docker compose exec -T postgres psql -U legal_user -d legal_ai_news
```

### Шаг 4: Запустить Reader Bot

```bash
# Запустить только reader_bot
docker compose up -d reader_bot

# Проверить логи
docker compose logs -f reader_bot

# Проверить что запущен
docker compose ps
```

### Шаг 5: Протестировать

1. Откройте Telegram
2. Найдите вашего бота `@legal_ai_news_reader_bot`
3. Отправьте `/start`
4. Пройдите онбординг (выбор тем, уровень, частота дайджестов)
5. Попробуйте команды:
   - `/today` - Персональные новости
   - `/search GDPR` - Поиск по слову
   - `/saved` - Сохранённые статьи
   - `/settings` - Настройки и статистика

---

## 📊 Структура БД

Reader Bot использует 4 новые таблицы:

### user_profiles
Профили пользователей с предпочтениями:
- `topics` - массив интересующих тем
- `expertise_level` - уровень экспертизы
- `digest_frequency` - частота дайджестов

### user_feedback
Фидбек на статьи (👍/👎):
- `is_useful` - понравилась ли статья
- `feedback_type` - причина если не понравилась

### user_interactions
История взаимодействий:
- `action` - тип (view, search, save, share)
- `search_query` - поисковый запрос

### saved_articles
Закладки пользователей

---

## 🔧 Команды для управления

```bash
# Запустить reader_bot
docker compose up -d reader_bot

# Остановить
docker compose stop reader_bot

# Перезапустить
docker compose restart reader_bot

# Посмотреть логи
docker compose logs -f reader_bot

# Логи за последние 100 строк
docker compose logs --tail 100 reader_bot

# Проверить использование памяти
docker stats legal_ai_reader_bot
```

---

## 📈 Мониторинг и аналитика

### Проверка пользователей:

```sql
-- Всего пользователей
SELECT COUNT(*) FROM user_profiles;

-- Активные пользователи
SELECT COUNT(*) FROM user_profiles WHERE is_active = TRUE;

-- Распределение по темам
SELECT
    UNNEST(topics) as topic,
    COUNT(*) as users
FROM user_profiles
GROUP BY topic
ORDER BY users DESC;

-- Распределение по уровню
SELECT
    expertise_level,
    COUNT(*) as count
FROM user_profiles
GROUP BY expertise_level;

-- Частота дайджестов
SELECT
    digest_frequency,
    COUNT(*) as count
FROM user_profiles
GROUP BY digest_frequency;
```

### Проверка engagement:

```sql
-- Топ сохраненных статей
SELECT
    p.id,
    pd.title,
    COUNT(sa.id) as saves_count
FROM saved_articles sa
JOIN publications p ON sa.publication_id = p.id
JOIN post_drafts pd ON p.draft_id = pd.id
GROUP BY p.id, pd.title
ORDER BY saves_count DESC
LIMIT 10;

-- Рейтинг статей по фидбеку
SELECT
    p.id,
    pd.title,
    COUNT(CASE WHEN uf.is_useful THEN 1 END) as likes,
    COUNT(CASE WHEN NOT uf.is_useful THEN 1 END) as dislikes
FROM user_feedback uf
JOIN publications p ON uf.publication_id = p.id
JOIN post_drafts pd ON p.draft_id = pd.id
GROUP BY p.id, pd.title
ORDER BY likes DESC
LIMIT 10;
```

---

## 🔍 Troubleshooting

### Бот не отвечает:

```bash
# Проверить что бот запущен
docker compose ps reader_bot

# Проверить логи на ошибки
docker compose logs reader_bot | grep ERROR

# Проверить токен
docker compose exec reader_bot env | grep READER_BOT_TOKEN
```

### Ошибка подключения к БД:

```bash
# Проверить что PostgreSQL запущен
docker compose ps postgres

# Проверить таблицы
docker compose exec postgres psql -U legal_user -d legal_ai_news \
  -c "\dt user_*"
```

### Миграция не применилась:

```bash
# Применить миграцию вручную
docker compose cp migrations/018_add_reader_tables.sql postgres:/tmp/
docker compose exec postgres psql -U legal_user -d legal_ai_news -f /tmp/018_add_reader_tables.sql
```

---

## 📝 Следующие шаги

После успешного запуска MVP:

1. **Тестирование**
   - Пройти полный онбординг
   - Протестировать все команды
   - Проверить персонализацию

2. **Дайджесты (Phase 2)**
   - Создать Celery tasks для дайджестов
   - Настроить расписание (daily/weekly)
   - Протестировать отправку

3. **Analytics (Phase 3)**
   - Dashboard для админа с метриками читателей
   - A/B тесты рекомендаций
   - Улучшение персонализации на основе фидбека

4. **Production**
   - Деплой на VDS (Hetzner CX21)
   - Настройка резервного копирования
   - Мониторинг и алерты

---

## 💡 FAQ

**Q: Можно ли использовать одну БД для обоих ботов?**
A: Да! Reader Bot использует ту же PostgreSQL БД что и Admin Bot.

**Q: Сколько памяти потребляет Reader Bot?**
A: ~150-200MB RAM (настроен лимит 200MB в docker-compose.yml)

**Q: Нужно ли отдельно деплоить на Vercel?**
A: Нет, Reader Bot работает в Docker рядом с Admin Bot.

**Q: Как обновить код Reader Bot?**
A: `git pull && docker compose restart reader_bot`

---

## 📞 Support

Если возникли вопросы или проблемы:

1. Проверьте логи: `docker compose logs reader_bot`
2. Проверьте БД: таблицы `user_*` должны существовать
3. Проверьте .env: токен `READER_BOT_TOKEN` должен быть валидным
4. Создайте issue в GitHub с описанием проблемы и логами
