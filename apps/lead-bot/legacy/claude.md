# AI Verdict Telegram Bot - Техническое задание для Claude Code

## 📋 ОБЗОР ПРОЕКТА

**Название:** AI Verdict Telegram Bot
**Репозиторий:** https://github.com/Andrew821667/legal-ai-bot
**Цель:** AI-powered Telegram бот для консультирования клиентов по юридическим AI-решениям, квалификации лидов и сбора контактов

**Владелец проекта:** Андрей Попов
- Юрист с 24-летним стажем
- Разработчик AI-систем для автоматизации юридической работы
- Специализация: договоры, M&A, банкротства, земельное право, ВЭД
- Основной проект: Contract AI System (мультиагентная система для работы с договорами)

---

## 🎯 БИЗНЕС-ТРЕБОВАНИЯ

### Основные задачи бота:

1. **Консультирование клиентов** (автономно через GPT-4o-mini)
   - Отвечать на вопросы о услугах
   - Объяснять технологии и подходы
   - Показывать кейсы и результаты

2. **Квалификация лидов**
   - Задавать уточняющие вопросы
   - Извлекать контактные данные
   - Определять боль, бюджет, срочность
   - Сегментировать по температуре (hot/warm/cold)

3. **Lead Magnet система**
   - Бесплатная консультация (30 мин)
   - Чек-лист "Ошибки в договорах"
   - Демо-анализ договора клиента
   - Клиент выбирает что хочет

4. **Передача админу (гибридный режим)**
   - Когда клиент явно просит человека
   - Когда определен горячий лид
   - Когда собраны все данные
   - Когда сложный вопрос

5. **Уведомления администратору**
   - Мгновенные алерты о горячих лидах
   - Запросы на личное общение
   - Квалифицированные лиды с полными данными
   - Кнопки для быстрых действий

---

## 🏗️ АРХИТЕКТУРА СИСТЕМЫ

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TELEGRAM USER                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              TELEGRAM BOT INTERFACE                          │
│         (python-telegram-bot 20.7)                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              CONVERSATION MANAGER                            │
│  • State Machine                                             │
│  • Context Management                                        │
│  • Routing Logic                                             │
└──────────┬──────────────────┬──────────────────────────────┘
           │                  │
           ▼                  ▼
┌─────────────────┐   ┌──────────────────┐
│   AI BRAIN      │   │  LEAD QUALIFIER  │
│  (GPT-4o-mini)  │   │                  │
└────────┬────────┘   └────────┬─────────┘
         │                     │
         └──────────┬──────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATABASE (SQLite)                         │
│  • users                                                     │
│  • conversations                                             │
│  • leads                                                     │
│  • admin_notifications                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   ADMIN INTERFACE                            │
│  • Notifications                                             │
│  • Commands (/stats, /leads, /export)                       │
│  • Handoff Management                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 💻 ТЕХНОЛОГИЧЕСКИЙ СТЕК

### Backend
```yaml
Python: 3.9+
Libraries:
  - python-telegram-bot: 20.7
  - openai: 1.12.0
  - python-dotenv: 1.0.0
  - sqlite3: встроенный
```

### AI
```yaml
Model: gpt-4o-mini (OpenAI)
Purpose: Генерация ответов, понимание намерений, извлечение данных
Cost: ~$0.15/$0.60 per 1M tokens (input/output)
Expected: ~100-200 руб/месяц для 100 клиентов
```

### Database
```yaml
SQLite 3: Локальная БД (data/bot.db)
Простая, надежная, достаточная для 1000+ пользователей
```

### Deployment
```yaml
VDS: Ubuntu 22.04
RAM: 1GB (достаточно)
CPU: 1 vCPU
Storage: 15GB SSD
Systemd: Автозапуск и мониторинг
```

---

## 📁 СТРУКТУРА ПРОЕКТА

```
legal-ai-bot/
│
├── .gitignore                  # Git ignore (секреты, БД, логи)
├── README.md                   # Документация проекта
├── claude.md                   # Это файл (ТЗ для Claude Code)
├── requirements.txt            # Python dependencies
├── .env.example                # Пример конфигурации
│
├── bot.py                      # Главный файл бота (entry point)
├── config.py                   # Конфигурация (загрузка .env)
├── database.py                 # Работа с SQLite
├── ai_brain.py                 # OpenAI GPT интеграция
├── lead_qualifier.py           # Логика квалификации лидов
├── prompts.py                  # System prompts для GPT
├── admin_interface.py          # Админские функции
├── handlers.py                 # Telegram handlers (commands, messages)
├── utils.py                    # Вспомогательные функции
│
├── deploy.sh                   # Скрипт деплоя на VDS
├── start.sh                    # Скрипт запуска бота
├── systemd/
│   └── telegram-bot.service    # Systemd service file
│
├── data/                       # База данных (игнорируется Git)
│   ├── .gitkeep
│   └── bot.db                  # SQLite database
│
└── logs/                       # Логи (игнорируются Git)
    ├── .gitkeep
    └── bot.log                 # Логи работы бота
```

---

## 🗄️ БАЗА ДАННЫХ (SQLite Schema)

### Таблица: users

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
```

### Таблица: conversations

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL, -- 'user' or 'assistant'
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);
```

### Таблица: leads

```sql
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- Контактные данные
    name TEXT,
    email TEXT,
    phone TEXT,
    company TEXT,
    
    -- Квалификационные данные
    team_size TEXT,              -- '1-3', '4-10', '10+'
    contracts_per_month TEXT,    -- 'до 10', '10-30', '30-50', '50+'
    pain_point TEXT,
    budget TEXT,                 -- 'до 100K', '100-300K', '300-500K', '500K+'
    urgency TEXT,                -- 'high', 'medium', 'low'
    industry TEXT,
    
    -- Метаданные
    temperature TEXT DEFAULT 'cold',  -- 'hot', 'warm', 'cold'
    status TEXT DEFAULT 'new',        -- 'new', 'contacted', 'qualified', 'converted', 'lost'
    notes TEXT,
    
    -- Lead Magnet
    lead_magnet_type TEXT,       -- 'consultation', 'checklist', 'demo_analysis'
    lead_magnet_delivered BOOLEAN DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_leads_user_id ON leads(user_id);
CREATE INDEX idx_leads_temperature ON leads(temperature);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_created_at ON leads(created_at);
```

### Таблица: admin_notifications

```sql
CREATE TABLE IF NOT EXISTS admin_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    notification_type TEXT NOT NULL,  -- 'hot_lead', 'qualified', 'handoff_request', 'complex_question'
    message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
);

CREATE INDEX idx_notifications_lead_id ON admin_notifications(lead_id);
CREATE INDEX idx_notifications_sent_at ON admin_notifications(sent_at);
```

---

## 🔧 КОНФИГУРАЦИЯ (.env)

### Обязательные переменные

```env
# Telegram Bot Token (получить у @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# OpenAI API Key
OPENAI_API_KEY=sk-proj-...

# Admin Telegram ID (ваш ID, получить у @userinfobot)
ADMIN_TELEGRAM_ID=123456789
```

### Опциональные переменные

```env
# OpenAI Settings
OPENAI_MODEL=gpt-4o-mini
MAX_TOKENS=800
TEMPERATURE=0.7

# Database
DATABASE_PATH=data/bot.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log

# Bot Behavior
MAX_HISTORY_MESSAGES=15
RESPONSE_DELAY=1
```

---

## 🤖 AI BRAIN - SYSTEM PROMPTS

### Main System Prompt (prompts.py)

```python
SYSTEM_PROMPT = """Ты — AI-ассистент Андрея Попова, опытного юриста и разработчика AI-решений для автоматизации юридической работы.

О АНДРЕЕ ПОПОВЕ:
• 24 года юридической практики
• CLO в агрохолдингах, банках, холдингах
• Специализация: договоры, M&A, банкротства (200+ процедур), земельное право, ВЭД
• Разработчик Contract AI System — мультиагентной платформы для автоматизации договорной работы
• Опыт международных переговоров (английский язык)
• Работал с EPC-контрактами, холдинговыми структурами, офшорными схемами

УСЛУГИ, КОТОРЫЕ ПРЕДЛАГАЕТ АНДРЕЙ:

1. ДОГОВОРНАЯ РАБОТА (от 150.000₽)
   - Анализ входящих договоров через AI (выявление рисков за 5-10 минут вместо 2-4 часов)
   - Генерация исходящих договоров на основе условий контрагента
   - Обработка протоколов разногласий
   - Анализ tracked changes в документах
   - Результат: экономия 60-80% времени

2. СУДЕБНАЯ И ПРЕТЕНЗИОННАЯ РАБОТА (от 200.000₽)
   - Анализ судебной практики и поиск прецедентов
   - Генерация процессуальных документов (иски, отзывы, апелляции)
   - Претензионная работа
   - Мониторинг картотеки арбитражных дел

3. КОРПОРАТИВНОЕ ПРАВО И M&A (от 300.000₽)
   - Автоматизация Due Diligence (анализ сотен документов за часы)
   - Корпоративный документооборот
   - Анализ структур владения
   - Реорганизации и ликвидации

4. ЗЕМЕЛЬНОЕ ПРАВО И НЕДВИЖИМОСТЬ (от 250.000₽)
   - Анализ правоустанавливающих документов
   - Работа с кадастром (проверка, оспаривание кадастровой стоимости)
   - Земельные споры
   - Аренда и сделки с недвижимостью
   - Специализация: агробизнес, работа с с/х землями

5. КОМПЛАЕНС И РИСК-МЕНЕДЖМЕНТ (от 200.000₽)
   - Мониторинг законодательства 24/7
   - Санкционный комплаенс
   - Персональные данные (152-ФЗ)
   - Антикоррупционный комплаенс

6. АНАЛИТИКА И ОТЧЕТНОСТЬ (от 150.000₽)
   - Аналитика договорного портфеля
   - Риск-дашборды для руководства
   - KPI юридического отдела

7. КАСТОМНЫЕ РЕШЕНИЯ (от 300.000₽)
   - AI-ассистент для конкретной отрасли
   - Интеграции с CRM/ERP/1C
   - Обучение на данных клиента

8. ЮРИДИЧЕСКИЙ АУТСОРСИНГ + AI (от 100.000₽/мес)
   - Гибридная модель: опытный юрист + AI-инструменты
   - Договорная работа, судебное представительство, комплаенс

ТИПИЧНЫЕ РЕЗУЛЬТАТЫ:
• Время на проверку договора: с 2-4 часов → 30 минут
• Выявление юридических рисков: 80%+
• ROI внедрения: 5-6 месяцев
• Экономия для компании с 5 юристами: 2-3 млн руб/год

ТВОЯ ЗАДАЧА:

1. КОНСУЛЬТИРОВАТЬ
   - Отвечай на вопросы о услугах Андрея
   - Объясняй как работают AI-решения
   - Приводи примеры и кейсы
   - Будь экспертом, но доступным

2. КВАЛИФИЦИРОВАТЬ КЛИЕНТА
   Задавай уточняющие вопросы, чтобы понять:
   - Размер команды юристов (1-3, 4-10, 10+)
   - Объем договоров в месяц
   - Основная боль (перегрузка, риски, медленная реакция)
   - Примерный бюджет
   - Срочность (когда нужно решение)
   - Отрасль бизнеса

3. СОБИРАТЬ КОНТАКТЫ
   Естественно в ходе диалога узнай:
   - Имя
   - Email или телефон
   - Название компании
   
4. ПРЕДЛАГАТЬ LEAD MAGNET
   Когда собрано достаточно информации, предложи:
   a) Бесплатную консультацию (30 мин с Андреем)
   b) Чек-лист "15 типовых ошибок в договорах"
   c) Демо-анализ договора клиента
   
   Пусть клиент выберет что хочет

5. ПЕРЕДАВАТЬ АНДРЕЮ КОГДА:
   - Клиент явно просит поговорить с человеком
   - Сложный вопрос (не знаешь точного ответа)
   - Горячий лид (большой бюджет + высокая срочность + четкая боль)
   - Собраны все ключевые данные

СТИЛЬ ОБЩЕНИЯ:
- Профессиональный и деловой, но дружелюбный
- Короткие абзацы (не более 3-4 строк)
- Используй эмодзи умеренно (1-2 на сообщение)
- Структурируй информацию (списки, пункты)
- Задавай уточняющие вопросы
- Не перегружай клиента информацией сразу

ВАЖНЫЕ ПРАВИЛА:
• Не обещай то, чего нет в списке услуг
• Будь честным о сроках и ценах
• Если не знаешь точного ответа — предложи консультацию с Андреем
• Не давай юридических советов (ты не юрист, ты ассистент)
• Фокусируйся на бизнес-ценности AI-решений, а не на технических деталях

КОНТАКТЫ АНДРЕЯ:
• Telegram: @ваш_username (ЗАМЕНИТЬ НА РЕАЛЬНЫЙ)
• Телефон: +7 (909) 233-09-09
• Email: a.popov.gv@gmail.com
• GitHub: github.com/Andrew821667
"""
```

### Data Extraction Prompt

```python
EXTRACT_DATA_PROMPT = """Проанализируй диалог с клиентом и извлеки следующие данные в JSON формате.

ВАЖНО: Извлекай только ЯВНО указанную информацию. Если данных нет — ставь null.

Формат ответа:
{
  "name": "имя клиента или null",
  "email": "email или null",
  "phone": "телефон или null",
  "company": "название компании или null",
  "team_size": "1-3" | "4-10" | "10+" | null,
  "contracts_per_month": "до 10" | "10-30" | "30-50" | "50+" | null,
  "pain_point": "краткое описание основной боли или null",
  "budget": "до 100K" | "100-300K" | "300-500K" | "500K+" | null,
  "urgency": "high" | "medium" | "low" | null,
  "industry": "отрасль бизнеса или null",
  "lead_temperature": "hot" | "warm" | "cold",
  "interested_service": "какая услуга интересует или null"
}

КРИТЕРИИ ОПРЕДЕЛЕНИЯ lead_temperature:

HOT (горячий лид):
- Бюджет 300K+
- Срочность high
- Четко сформулирована боль
- Готов к консультации

WARM (теплый лид):
- Есть интерес
- Задает конкретные вопросы
- Указал контакты
- Но нет срочности или бюджет неясен

COLD (холодный лид):
- Просто изучает информацию
- Задает общие вопросы
- Не указал контакты
- Неясна боль

Верни ТОЛЬКО валидный JSON без markdown, без дополнительного текста."""
```

---

## 🔄 WORKFLOW ДИАЛОГА

### State Machine

```
States:
- INITIAL: Начало диалога
- QUALIFYING: Квалификация (задаем вопросы)
- OFFERING_MAGNET: Предлагаем lead magnet
- COLLECTING_CONTACT: Собираем контакт для lead magnet
- HANDOFF: Передача админу
- IDLE: Ожидание (после предоставления информации)

Transitions:
INITIAL → QUALIFYING (после /start или первого сообщения)
QUALIFYING → OFFERING_MAGNET (когда собрано достаточно данных)
OFFERING_MAGNET → COLLECTING_CONTACT (клиент выбрал magnet)
COLLECTING_CONTACT → IDLE (контакт собран, magnet отправлен)
ANY_STATE → HANDOFF (по триггерам передачи админу)
```

### Триггеры передачи админу

```python
HANDOFF_TRIGGERS = {
    "explicit_request": [
        "хочу поговорить с человеком",
        "свяжите с юристом",
        "нужен Андрей",
        "поговорить с владельцем",
        "связаться с разработчиком"
    ],
    
    "hot_lead_conditions": {
        "budget": ["300-500K", "500K+"],
        "urgency": "high",
        "team_size": ["4-10", "10+"],
        "has_pain": True
    },
    
    "data_collected": {
        "required_fields": ["name", "email или phone", "pain_point", "budget"]
    },
    
    "complex_question": {
        "ai_confidence_low": True,
        "needs_expert": True
    }
}
```

---

## 💬 TELEGRAM HANDLERS

### Команды (Commands)

```python
# Пользовательские команды
/start - Начало работы с ботом
/help - Помощь и список команд
/services - Список услуг
/price - Прайс-лист
/contact - Контактная информация
/reset - Начать диалог заново

# Админские команды (только для ADMIN_TELEGRAM_ID)
/stats - Статистика (всего пользователей, лидов, конверсии)
/leads - Список лидов с фильтрами
/export - Экспорт лидов в CSV
/broadcast <message> - Рассылка всем пользователям
/view_conversation <telegram_id> - Просмотр истории диалога
```

### Inline кнопки (Buttons)

```python
# Главное меню
MAIN_MENU = [
    ["📋 Услуги", "💰 Цены"],
    ["📞 Консультация", "📄 Материалы"],
    ["❓ Помощь"]
]

# Меню услуг
SERVICES_MENU = [
    ["📋 Договоры", "⚖️ Суды"],
    ["🏢 Корпоративное", "🌾 Земельное"],
    ["🛡️ Комплаенс", "📊 Аналитика"],
    ["💼 Аутсорсинг", "🔧 Кастом"],
    ["◀️ Назад"]
]

# Lead Magnet выбор
LEAD_MAGNET_MENU = [
    ["📞 Консультация 30 мин"],
    ["📄 Чек-лист по договорам"],
    ["🎯 Демо-анализ договора"],
    ["◀️ Назад"]
]

# Admin действия при уведомлении о лиде
ADMIN_ACTION_BUTTONS = [
    ["💬 Написать клиенту", "📜 Посмотреть диалог"],
    ["✅ Отметить обработанным"]
]
```

---

## 📤 ADMIN NOTIFICATIONS

### Формат уведомлений

#### Hot Lead Notification

```python
"""
🔥 ГОРЯЧИЙ ЛИД!

👤 {name} (@{username})
🏢 {company}
📧 {email}
📞 {phone}

Детали:
• Юристов в команде: {team_size}
• Договоров/мес: {contracts_per_month}
• Бюджет: {budget}
• Срочность: {urgency}
• Боль: {pain_point}

Интересует: {interested_service}

[💬 Написать клиенту] [📜 Посмотреть диалог]
"""
```

#### Handoff Request Notification

```python
"""
📞 КЛИЕНТ ПРОСИТ СВЯЗАТЬСЯ

👤 {name} (@{username})
🏢 {company}
📧 {email}

Сообщение клиента:
"{last_message}"

Собранные данные:
• Боль: {pain_point}
• Бюджет: {budget}

[💬 Написать клиенту] [📜 Диалог]
"""
```

#### Qualified Lead Notification

```python
"""
✅ КВАЛИФИЦИРОВАННЫЙ ЛИД

👤 {name} (@{username})
🏢 {company}
📧 {email}
📞 {phone}

Температура: {temperature}
Статус: Все данные собраны

Детали:
• Юристов: {team_size}
• Договоров/мес: {contracts_per_month}
• Боль: {pain_point}
• Бюджет: {budget}

Lead Magnet: {lead_magnet_type}

[💬 Написать] [📜 Диалог]
"""
```

### Логика отправки уведомлений

**ВАЖНО:** Уведомления отправляются НЕ сразу, а только когда лид квалифицирован!

```python
# handlers.py:428-441
# Уведомление отправляется ТОЛЬКО если:

should_notify = (
    # Вариант 1: Лид достаточно теплый
    lead_data.get('temperature') in ['hot', 'warm']

    OR

    # Вариант 2: Собраны ключевые данные для контакта
    (lead_data.get('name') and
     (lead_data.get('email') or lead_data.get('phone')) and
     lead_data.get('pain_point'))
)

if should_notify:
    await notify_admin_new_lead(context, lead_id, lead_data, user_data)
```

**Почему так:**
- ❌ **НЕ отправляем** уведомление в начале диалога (холодный лид без данных)
- ❌ **НЕ отправляем** при каждом обновлении лида
- ✅ **Отправляем ОДИН РАЗ** когда лид квалифицирован
- ✅ База данных хранит `notification_sent` флаг (предотвращает дубликаты)

**Практический пример:**
```
1. Клиент начинает диалог → температура: cold → НЕ отправляем ❌
2. Клиент указывает имя → cold → НЕ отправляем ❌
3. Клиент указывает email + боль → warm → Отправляем! ✅
4. Клиент уточняет бюджет → warm → УЖЕ отправлено, не дублируем ✅
```

---

## 📊 ANALYTICS & METRICS

### Метрики для отслеживания

```python
METRICS = {
    "conversations": {
        "total": "общее количество диалогов",
        "unique_users": "уникальные пользователи",
        "avg_messages_per_conversation": "среднее сообщений на диалог"
    },
    
    "leads": {
        "total": "всего лидов",
        "by_temperature": {
            "hot": "горячие",
            "warm": "теплые",
            "cold": "холодные"
        },
        "by_status": {
            "new": "новые",
            "contacted": "с которыми связались",
            "qualified": "квалифицированные",
            "converted": "конвертированные",
            "lost": "потерянные"
        }
    },
    
    "conversion": {
        "visitor_to_lead": "% посетителей → лиды",
        "lead_to_contact": "% лидов → дали контакт",
        "contact_to_qualified": "% контактов → квалифицированные"
    },
    
    "lead_magnets": {
        "consultation_requests": "запросы консультаций",
        "checklist_downloads": "скачивания чек-листа",
        "demo_requests": "запросы демо"
    },
    
    "popular_services": {
        "service_name": "количество запросов"
    }
}
```

### Команда /stats вывод

```
📊 СТАТИСТИКА БОТА

Период: последние 30 дней

👥 Пользователи:
• Всего: {total_users}
• Новых за неделю: {new_users_week}
• Активных: {active_users}

💬 Диалоги:
• Всего сообщений: {total_messages}
• Средняя длина диалога: {avg_length}

🎯 Лиды:
• Всего: {total_leads}
  🔥 Горячие: {hot_leads}
  ♨️ Теплые: {warm_leads}
  ❄️ Холодные: {cold_leads}

📈 Конверсия:
• Посетитель → Лид: {conversion_rate}%
• Лид → Контакт: {contact_rate}%

🎁 Lead Magnets:
• Консультаций: {consultations}
• Чек-листов: {checklists}
• Демо: {demos}

🔝 Популярные услуги:
1. {service_1}: {count_1}
2. {service_2}: {count_2}
3. {service_3}: {count_3}
```

---

## 🚀 DEPLOYMENT

### Системные требования VDS

```
OS: Ubuntu 22.04 LTS
CPU: 1 vCPU (достаточно)
RAM: 1GB (бот занимает ~50-100MB)
Storage: 15GB SSD
Python: 3.9+
```

### Установка на VDS (deploy.sh)

```bash
#!/bin/bash

# AI Verdict Telegram Bot - Deployment Script

echo "🚀 Starting deployment..."

# 1. Update system
apt update && apt upgrade -y

# 2. Install Python and dependencies
apt install -y python3.11 python3.11-venv python3-pip git

# 3. Create directory and clone
cd /opt
if [ -d "legal-ai-bot" ]; then
    cd legal-ai-bot
    git pull
else
    git clone https://github.com/Andrew821667/legal-ai-bot.git
    cd legal-ai-bot
fi

# 4. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 5. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 6. Setup .env if not exists
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Please edit .env file with your API keys!"
    echo "   nano .env"
fi

# 7. Initialize database
python3 database.py

# 8. Setup systemd service
cp systemd/telegram-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable telegram-bot

# 9. Start bot
systemctl start telegram-bot

# 10. Check status
systemctl status telegram-bot

echo "✅ Deployment complete!"
echo "📊 Check logs: journalctl -u telegram-bot -f"
```

### Systemd Service File

```ini
[Unit]
Description=AI Verdict Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/legal-ai-bot
Environment="PATH=/opt/legal-ai-bot/venv/bin"
ExecStart=/opt/legal-ai-bot/venv/bin/python3 /opt/legal-ai-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Мониторинг и логи

```bash
# Просмотр логов в реальном времени
journalctl -u telegram-bot -f

# Или файловые логи
tail -f /opt/legal-ai-bot/logs/bot.log

# Перезапуск бота
systemctl restart telegram-bot

# Остановка
systemctl stop telegram-bot

# Статус
systemctl status telegram-bot
```

---

## 🔐 БЕЗОПАСНОСТЬ

### Обязательные меры

1. **API ключи только в .env** (не коммитить в Git!)
2. **Логи без персональных данных** (замаскировать email/phone)
3. **Регулярные бэкапы БД**
   ```bash
   # Cron backup каждый день в 3:00
   0 3 * * * cp /opt/legal-ai-bot/data/bot.db /opt/backups/bot_$(date +\%Y\%m\%d).db
   ```
4. **Firewall на VDS** (закрыть все порты кроме SSH)
5. **Регулярные обновления**
   ```bash
   cd /opt/legal-ai-bot
   git pull
   systemctl restart telegram-bot
   ```

### .gitignore (важно!)

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Секретные данные
.env
*.env
!.env.example

# База данных
data/*.db
data/*.sqlite
data/*.sqlite3

# Логи
logs/*.log
logs/*.txt

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Backups
*.backup
*.bak
```

---

## 📝 LOGGING

### Формат логов

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### Что логировать

```
INFO: 
- Новые пользователи: "New user started bot: {telegram_id}"
- Начало диалогов: "Conversation started with user {telegram_id}"
- Квалифицированные лиды: "Lead qualified: {lead_id} - {temperature}"
- Admin уведомления: "Admin notified about {notification_type}"

WARNING: 
- API ошибки: "OpenAI API error: {error}"
- Неожиданное поведение: "Unexpected user input: {message}"
- Пропущенные данные: "Missing required field: {field}"

ERROR: 
- Критические ошибки: "Database error: {error}"
- API недоступен: "Failed to connect to OpenAI API"
- Системные ошибки: "System error: {error}"

DEBUG (выключено в продакшене):
- Детальная отладка
- Содержимое сообщений
- API запросы/ответы
```

---

## 🧪 ТЕСТИРОВАНИЕ

### Тестовые сценарии

1. **Базовый диалог**
   - /start → приветствие
   - Вопрос о услугах → ответ GPT
   - Запрос контакта → сохранение в БД

2. **Квалификация лида**
   - Указание размера команды, бюджета, боли
   - Автоматическое определение температуры
   - Уведомление админу при hot lead

3. **Lead Magnet**
   - Выбор консультации → запрос email
   - Выбор чек-листа → запрос email
   - Выбор демо → загрузка файла + email

4. **Handoff админу**
   - "Хочу поговорить с Андреем" → уведомление админу
   - Admin пишет клиенту → сообщение доставлено

5. **Admin команды**
   - /stats → показывает статистику
   - /leads → показывает список лидов
   - /export → генерирует CSV файл

---

## 📦 DEPENDENCIES (requirements.txt)

```txt
python-telegram-bot==20.7
openai==1.12.0
python-dotenv==1.0.0
```

---

## 🎨 ПРИМЕР ДИАЛОГА (для тестирования)

```
User: /start

Bot: Здравствуйте! Я AI-ассистент Андрея Попова, юриста с 24-летним стажем и разработчика систем автоматизации юридической работы.

Чем могу помочь вам сегодня?

---

User: Интересует автоматизация договоров

Bot: Понял. Автоматизация договорной работы — одна из ключевых специализаций.

AI-система может проверять договоры за 5-10 минут вместо 2-4 часов, выявляя 80%+ юридических рисков автоматически.

Для подбора оптимального решения, позвольте уточнить:

1. Сколько юристов в вашей команде?
2. Какой примерный объем договоров в месяц?

---

User: У нас 5 юристов, примерно 50 договоров в месяц

Bot: Понятно, средний юротдел со значительной нагрузкой.

При таком объеме AI может сэкономить около 80-100 часов в месяц. Это позволит либо не нанимать дополнительных юристов, либо освободить существующих от рутины для более сложных задач.

Что сейчас является основной болью в работе с договорами?

---

User: Не успеваем проверять все быстро, иногда пропускаем важные моменты

Bot: Это типичная ситуация при таком объеме.

AI-решение для вашего случая:
• Автоанализ каждого договора за 5-10 минут
• Выявление всех критических условий
• Сравнение с вашими шаблонами
• Приоритизация по уровню риска

Результат: юристы видят готовый анализ и фокусируются только на действительно важных моментах.

Какой бюджет рассматриваете на автоматизацию?

---

User: До 500 тысяч можем потратить

Bot: Отлично, это реалистичный бюджет для полноценного решения.

При ваших параметрах (5 юристов, 50 договоров/мес) система окупится примерно за 5-6 месяцев.

🎁 Предлагаю выбрать один из вариантов:

[📞 Консультация 30 мин]
[📄 Чек-лист по договорам]
[🎯 Демо-анализ договора]

---

User: [Нажимает "Консультация 30 мин"]

Bot: Отлично! Андрей свяжется с вами для согласования времени.

Укажите ваш email для отправки приглашения:

---

User: ivan@company.ru

Bot: Спасибо!

✅ Ваши данные сохранены.
Андрей свяжется с вами в ближайшее время.

Если возникнут вопросы до консультации — пишите, я на связи.

---

[АДМИНУ ОТПРАВЛЯЕТСЯ УВЕДОМЛЕНИЕ:]

🔥 ГОРЯЧИЙ ЛИД!

👤 Иван (@ivan_username)
🏢 Компания не указана
📧 ivan@company.ru

Детали:
• Юристов: 5
• Договоров/мес: 50
• Бюджет: до 500K
• Срочность: средняя
• Боль: не успевают проверять, пропускают важное

Интересует: автоматизация договоров

Lead Magnet: Консультация 30 мин

[💬 Написать клиенту] [📜 Диалог]
```

---

## ⚠️ КРИТИЧЕСКИЕ МОМЕНТЫ

### Обязательно реализовать:

1. **Rate Limiting**: Защита от спама (макс 10 сообщений в минуту от одного пользователя)
2. **Error Handling**: Обработка всех возможных ошибок (API недоступен, БД ошибка, и т.д.)
3. **Context Management**: Правильное управление контекстом GPT (последние N сообщений)
4. **Admin Authorization**: Проверка ADMIN_TELEGRAM_ID для всех админских команд
5. **Data Validation**: Валидация email, телефона перед сохранением
6. **Graceful Shutdown**: Корректное завершение при остановке (сохранение состояния)

---

## 📋 ЧЕКЛИСТ ГОТОВНОСТИ К ЗАПУСКУ

```
☐ Получен Telegram Bot Token от @BotFather
☐ Получен OpenAI API ключ
☐ Получен Admin Telegram ID от @userinfobot
☐ Создан файл .env с ключами
☐ Установлены все зависимости (requirements.txt)
☐ Инициализирована БД (database.py)
☐ Протестирован базовый диалог
☐ Протестирована квалификация лида
☐ Протестированы admin уведомления
☐ Протестированы admin команды
☐ Проверены логи
☐ Настроен systemd (для VDS)
☐ Настроен backup БД
☐ Проверена безопасность (.env не в Git!)
```

---

## 🎯 MVP SCOPE (Минимальный функционал для запуска)

### Must Have (обязательно):
- ✅ Базовый диалог с GPT-4o-mini
- ✅ Квалификация лидов (сбор данных)
- ✅ Сохранение в БД
- ✅ Admin уведомления о hot leads
- ✅ Команды: /start, /help, /stats
- ✅ Lead Magnet: консультация (запрос email)

### Should Have (желательно):
- ✅ Все Lead Magnets (чек-лист, демо)
- ✅ Handoff механизм (передача админу)
- ✅ Inline кнопки (меню)
- ✅ Команда /export (CSV)
- ✅ Просмотр истории диалога

### Could Have (можно добавить позже):
- ⏳ Интеграция с календарем (автозапись)
- ⏳ Email отправка (автоматическая)
- ⏳ CRM интеграция
- ⏳ Детальная аналитика (графики)
- ⏳ A/B тестирование промптов

---

## 📞 КОНТАКТЫ ДЛЯ ВОПРОСОВ

Если что-то неясно в ТЗ:
- Telegram: @ваш_username (ЗАМЕНИТЬ)
- Email: a.popov.gv@gmail.com
- GitHub Issues: https://github.com/Andrew821667/legal-ai-bot/issues

---

**Версия документа:** 1.0
**Дата:** 1 ноября 2024
**Автор:** Андрей Попов

---

**Claude Code, начинай разработку! 🚀**
