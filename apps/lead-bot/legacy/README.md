# AI Verdict Telegram Bot

> ⚠️ Этот README относится к историческому standalone-контуру.
> Для актуального запуска в монорепозитории используйте корневой README (`/README.md`) и runbook (`/docs/runbook.md`).

AI-powered Telegram бот для консультирования клиентов по юридическим AI-решениям, квалификации лидов и сбора контактов.

## Возможности

- 🤖 **AI-диалог** через GPT-4o-mini
- 🎯 **Квалификация лидов** (hot/warm/cold)
- 📊 **Автоматический сбор** контактов и данных
- 🎁 **Lead Magnet система** (консультация, чек-лист, демо)
- 📢 **Уведомления админу** о важных событиях
- 📈 **Аналитика** и статистика
- 💾 **Экспорт лидов** в CSV

## Технологии

- Python 3.9+
- python-telegram-bot 20.7
- OpenAI GPT-4o-mini
- SQLite 3

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/Andrew821667/legal-ai-bot.git
cd legal-ai-bot
```

### 2. Получение API ключей

Вам понадобятся:

1. **Telegram Bot Token** - получить у [@BotFather](https://t.me/BotFather)
   - Отправьте `/newbot`
   - Следуйте инструкциям
   - Сохраните полученный токен

2. **OpenAI API Key** - получить на [platform.openai.com](https://platform.openai.com/api-keys)
   - Зарегистрируйтесь или войдите
   - Создайте новый API ключ
   - Сохраните ключ

3. **Admin Telegram ID** - получить у [@userinfobot](https://t.me/userinfobot)
   - Отправьте `/start`
   - Скопируйте ваш ID

### 3. Настройка конфигурации

```bash
# Создайте .env файл из примера
cp .env.example .env

# Отредактируйте .env и добавьте ваши ключи
nano .env
```

Заполните обязательные переменные в `.env`:
```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
OPENAI_API_KEY=ваш_llm_api_key
ADMIN_TELEGRAM_ID=ваш_telegram_id
```

### 4. Запуск бота

```bash
# Перейдите в папку проекта
cd legal-ai-bot

# Запустите бот
./start.sh
```

Скрипт `start.sh` автоматически:
- Создаст виртуальное окружение
- Установит зависимости
- Инициализирует базу данных
- Запустит бота

Для остановки нажмите `Ctrl+C`

## Деплой на VDS (Ubuntu 22.04)

### Автоматический деплой

```bash
# На вашем VDS сервере
sudo bash deploy.sh
```

Скрипт автоматически:
- Обновит систему
- Установит Python 3.11 и зависимости
- Склонирует репозиторий в `/opt/legal-ai-bot`
- Настроит виртуальное окружение
- Инициализирует БД
- Установит systemd сервис

### После деплоя

1. Отредактируйте `.env` с вашими ключами:
```bash
sudo nano /opt/legal-ai-bot/.env
```

2. Запустите бота:
```bash
sudo systemctl start telegram-bot
```

3. Проверьте статус:
```bash
sudo systemctl status telegram-bot
```

4. Просмотр логов в реальном времени:
```bash
sudo journalctl -u telegram-bot -f
```

### Управление сервисом

```bash
# Запуск
sudo systemctl start telegram-bot

# Остановка
sudo systemctl stop telegram-bot

# Перезапуск
sudo systemctl restart telegram-bot

# Статус
sudo systemctl status telegram-bot

# Автозапуск при перезагрузке (уже включен)
sudo systemctl enable telegram-bot
```

## CI/CD - Автоматический деплой через GitHub Actions

Проект настроен для автоматического деплоя при push в main ветку.

### Что происходит при push:

1. **Запускаются тесты** - проверка всех модулей
2. **Деплой на VDS** - если тесты прошли
3. **Health check** - проверка что бот работает

### Настройка CI/CD

Для работы автоматического деплоя нужно настроить GitHub Secrets:

**Обязательные секреты:**
- `VDS_HOST` - IP адрес VDS сервера
- `VDS_USERNAME` - пользователь на VDS (обычно `root`)
- `VDS_SSH_PRIVATE_KEY` - SSH приватный ключ для подключения
- `TELEGRAM_BOT_TOKEN` - токен бота (для health check)
- `OPENAI_API_KEY` - OpenAI API ключ (для тестов)
- `ADMIN_TELEGRAM_ID` - ID админа (для тестов)

**Опциональные:**
- `VDS_PORT` - SSH порт (по умолчанию 22)

### Настройка SSH ключей

Для безопасного деплоя используются SSH ключи вместо пароля.

**Подробная инструкция:** [SSH_SETUP.md](SSH_SETUP.md)

### Просмотр логов деплоя

https://github.com/Andrew821667/legal-ai-bot/actions

## Пользовательские команды

- `/start` - Начало работы с ботом
- `/help` - Справка и список команд
- `/reset` - Начать диалог заново

## Админские команды

Доступны только пользователю с ID из `ADMIN_TELEGRAM_ID`:

- `/stats` - Статистика бота (пользователи, лиды, конверсия)
- `/leads` - Список всех лидов
- `/leads hot` - Список горячих лидов
- `/leads warm` - Список теплых лидов
- `/export` - Экспорт лидов в CSV
- `/view_conversation <telegram_id>` - Просмотр истории диалога

## Структура проекта

```
legal-ai-bot/
├── bot.py                  # Главный файл запуска
├── handlers.py             # Обработчики Telegram
├── ai_brain.py             # Интеграция с OpenAI
├── lead_qualifier.py       # Квалификация лидов
├── admin_interface.py      # Админские функции
├── database.py             # Работа с SQLite
├── config.py               # Конфигурация
├── prompts.py              # System prompts для GPT
├── utils.py                # Вспомогательные функции
├── requirements.txt        # Python зависимости
├── .env.example            # Пример конфигурации
├── deploy.sh               # Скрипт деплоя на VDS
├── start.sh                # Скрипт локального запуска
├── systemd/
│   └── telegram-bot.service  # Systemd сервис
├── data/
│   └── bot.db              # SQLite база данных
└── logs/
    └── bot.log             # Логи работы бота
```

## База данных

SQLite база данных автоматически создается при первом запуске.

Таблицы:
- `users` - пользователи бота
- `conversations` - история диалогов
- `leads` - квалифицированные лиды
- `admin_notifications` - уведомления админу

## Разработка

### Установка зависимостей для разработки

```bash
cd legal-ai-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Запуск для разработки

```bash
python bot.py
```

### Тестирование модулей

```bash
# Тест базы данных
python database.py

# Тест AI brain
python ai_brain.py

# Тест lead qualifier
python lead_qualifier.py
```

## Troubleshooting

### Ошибка: "TELEGRAM_BOT_TOKEN не установлен"

Убедитесь что:
1. Создан файл `.env` в корне проекта
2. В `.env` добавлен `TELEGRAM_BOT_TOKEN=ваш_токен`
3. Токен скопирован полностью без пробелов

### Ошибка: "OPENAI_API_KEY не установлен"

Проверьте:
1. API ключ добавлен в `.env`
2. Ключ соответствует выбранному провайдеру и не пустой
3. На аккаунте OpenAI есть средства или активная подписка

### Бот не отвечает на сообщения

1. Проверьте логи: `tail -f logs/bot.log`
2. Убедитесь что бот запущен
3. Проверьте интернет соединение
4. Убедитесь что токен правильный (тест в @BotFather)

### База данных не создается

```bash
# Попробуйте создать вручную
python database.py

# Проверьте права доступа к папке data/
chmod 755 data/
```

## Безопасность

⚠️ **Важно:**

1. Никогда не коммитьте `.env` файл в git
2. Храните API ключи в безопасности
3. Регулярно делайте бэкап базы данных:
   ```bash
   cp data/bot.db backups/bot_$(date +%Y%m%d).db
   ```
4. На VDS используйте firewall (закройте все порты кроме SSH)

## Мониторинг

### Просмотр логов

```bash
# Локально
tail -f logs/bot.log

# На VDS через systemd
sudo journalctl -u telegram-bot -f

# Последние 100 строк
sudo journalctl -u telegram-bot -n 100
```

### Проверка работы

```bash
# Статус сервиса
sudo systemctl status telegram-bot

# Использование ресурсов
top -p $(pgrep -f bot.py)
```

## Лицензия

MIT License - см. файл [LICENSE](LICENSE)

## Автор

Андрей Попов
- Telegram: @AndrewPopov821667
- Email: a.popov.gv@gmail.com
- GitHub: [@Andrew821667](https://github.com/Andrew821667)
- 
---

**Update (2025-12-23):** OpenAI API key updated for CI/CD pipeline restoration.

---

**Claude Code** использовался для разработки этого проекта.
