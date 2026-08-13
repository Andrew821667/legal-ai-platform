# AI Verdict Platform

**AI-платформа для юридического бизнеса** — лидогенерация, анализ договоров, новостная аналитика и автоматизация коммуникаций через единый контур Telegram-ботов, веб-сайта и API.

**Сайт:** [ai-verdict.ru](https://ai-verdict.ru) · **Contract AI:** [contract.ai-verdict.ru](https://contract.ai-verdict.ru)

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![Monorepo](https://img.shields.io/badge/UV-Workspace-purple.svg)](https://docs.astral.sh/uv/)

---

## Что это

AI Verdict Platform — это продуктовая экосистема для юридического рынка. Платформа объединяет AI-анализ договоров, автоматическую лидогенерацию через Telegram, новостную аналитику и веб-витрину в единую систему с общим бэкендом и базой пользователей.

### Бизнес-модель

```
Пользователь                                    Результат
    │                                                │
    ├── Telegram-бот ──── AI-консультация ──────── Квалифицированный лид
    │                  └── Анализ договора ──────── Отчёт о рисках
    │
    ├── Веб-сайт ──────── Лендинги продуктов ───── Заявка на пилот
    │                  └── SSO в Contract AI ────── Бесшовный вход
    │
    ├── Новостной бот ─── Персональная лента ───── Вовлечение / nurturing
    │
    └── Mini App ──────── Инструменты / кейсы ──── Конверсия в клиента
```

---

## Продукты платформы

### Telegram Lead Bot

AI-ассистент для консультирования и квалификации клиентов:

- Автономные консультации через GPT-4o-mini
- Квалификация лидов: боль, бюджет, срочность, размер команды
- Lead magnet система: консультация, чек-лист, демо-анализ
- **Анализ договоров прямо в Telegram** — пользователь отправляет файл и получает отчёт с рисками и рекомендациями
- Гибридный режим: бот + передача живому юристу
- Уведомления администратору о горячих лидах

### Contract AI Integration

Бесшовная интеграция с [Contract AI System](https://github.com/Andrew821667/Contract-AI-System-):

- **Bridge API** — proxy-слой в core-api для обращений к Contract AI System
- **SSO** — единый вход: пользователь платформы автоматически авторизуется в Contract AI
- **Telegram flow** — загрузка договора в бот, отслеживание прогресса, краткий отчёт
- **Статус-мониторинг** — проверка доступности Contract AI System (online/busy/offline)

### Новостная система

Автоматическая генерация и публикация юридических AI-новостей:

- Мониторинг источников + LLM-фильтрация релевантности
- Генерация постов для Telegram-канала
- Reader-бот с персонализированной лентой и поиском
- Admin-бот для управления публикациями

### Веб-сайт

Next.js-сайт с продуктовыми лендингами:

- Маршруты для юристов и бизнеса
- Страница Contract AI System с SSO-входом
- Mini App для Telegram WebApp (инструменты, кейсы, решения)
- CTA-фреймворк с deep links в ботов

---

## Архитектура

Монорепозиторий на UV workspace:

```
legal-ai-platform/
├── apps/
│   ├── core-api/              # Единый FastAPI бэкенд
│   │   ├── routers/           # 12 роутеров (leads, contracts, bridge, admin...)
│   │   ├── models/            # SQLAlchemy + Alembic миграции
│   │   └── auth.py            # API Key авторизация
│   │
│   ├── lead-bot/              # Telegram-бот лидогенерации
│   │   ├── handlers/          # 27 модулей обработчиков
│   │   │   ├── contract_analysis.py  # Анализ договоров через bridge
│   │   │   ├── user.py              # Основной user flow
│   │   │   └── business.py          # Business-mode (B2B)
│   │   ├── core_api_bridge.py # Синхронизация с core-api
│   │   └── ai_brain.py        # GPT-4o-mini интеграция
│   │
│   ├── news/                  # Генератор + паблишер + admin-бот новостей
│   ├── news/legacy/           # Reader-бот (персонализация, поиск)
│   ├── contract-worker/       # Воркер анализа (standalone)
│   ├── contract-ai/           # Reference-контур Contract AI System
│   │
│   └── web/                   # Next.js 16 сайт
│       ├── app/               # App Router (10+ маршрутов)
│       ├── components/        # React-компоненты
│       └── lib/links.ts       # Маршрутизация + SSO helpers
│
├── packages/
│   ├── shared/                # Общие схемы и типы
│   └── prompts/               # Shared промпты
│
├── infra/
│   ├── compose/               # Docker Compose (dev + prod)
│   └── scripts/               # Deploy, backup, тесты
│
├── docs/                      # Документация (30+ файлов)
├── pyproject.toml             # UV workspace root
└── Makefile                   # lint, test, dev, prod, deploy
```

---

## Технологический стек

| Слой | Технологии |
|------|-----------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, Alembic |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS, Framer Motion |
| **Telegram** | python-telegram-bot 20.7, GPT-4o-mini |
| **Database** | PostgreSQL 16 |
| **LLM** | GPT-4o-mini (бот), DeepSeek/Claude/GPT-4o (анализ через Contract AI) |
| **Infra** | Docker Compose, UV workspace, Ruff, pytest |
| **Monitoring** | Telegram alerts, structured logging |

---

## Быстрый старт

### Dev-окружение

```bash
# Зависимости
uv sync

# Инфраструктура (PostgreSQL)
docker compose -f infra/compose/docker-compose.dev.yml up --build

# Или по компонентам:
make dev        # Всё сразу
make lint       # Линтинг (runtime-критичные правила)
make test       # Тесты
```

### Production

```bash
make prod       # Собрать и запустить production stack
make deploy     # Pull → migrate → restart
```

### Конфигурация

```bash
cp .env.example .env
# Минимум: TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, DATABASE_URL
# Для Contract AI: CONTRACT_AI_BRIDGE_SECRET, CONTRACT_AI_BRIDGE_*_URL
```

---

## Интеграция с Contract AI System

Платформа взаимодействует с [Contract AI System](https://github.com/Andrew821667/Contract-AI-System-) через Bridge API:

```
Telegram-бот                   core-api                    Contract AI System
     │                            │                              │
     │  файл договора             │                              │
     ├──────────────────────────► │  POST /contract-ai/analyze   │
     │                            ├─────────────────────────────►│
     │                            │                              │ анализ...
     │  прогресс 40%...           │  GET /contract-ai/progress   │
     │◄────────────────────────── │◄─────────────────────────────│
     │                            │                              │
     │  краткий отчёт             │  GET /contract-ai/summary    │
     │◄────────────────────────── │◄─────────────────────────────│
     │                            │                              │
```

Веб-сайт использует SSO для бесшовного входа в Contract AI System.

---

## Связанные проекты

- **[Contract AI System](https://github.com/Andrew821667/Contract-AI-System-)** — AI-collaborative contract operating system. Полнотекстовый анализ договоров, мультимодельный LLM-каскад, агентная оркестрация.

---

## Документация

| Документ | Описание |
|----------|----------|
| `docs/architecture.md` | Runtime-архитектура |
| `docs/runbook.md` | Эксплуатация и деплой |
| `docs/contract-analyzer.md` | Алгоритм анализа договоров |
| `docs/project-control-checklist.md` | Статус и остаток работ |

---

## Автор

**Андрей Попов** — юрист (24 года практики) и разработчик AI-систем для автоматизации юридической работы.

- GitHub: [@Andrew821667](https://github.com/Andrew821667)
- Проект: [AI Verdict](https://ai-verdict.ru)

---

## Лицензия

MIT License — см. [LICENSE](LICENSE)
