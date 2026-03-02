# Архитектура legal-ai-platform

## Компоненты
- `core-api` — единый backend на FastAPI, единственный источник истины.
- `postgres` — основное хранилище (без включенного pgvector на старте).
- `lead-bot` — Telegram-бот для сбора лидов, с локальным SQLite fallback-буфером.
- `news`:
  - `news.generate` — тяжёлый batch-джоб по расписанию.
  - `news.publish` — лёгкий cron-паблишер.
  - `news.admin_bot` — Telegram админ-панель управления автоматизациями.
- `contract-worker` — воркер анализа договоров на MacBook.
- `caddy` — reverse proxy и автогенерация TLS.
- `automation control plane` — таблица `automation_controls` + API для runtime-тумблеров автоматизаций.

## Всегда включено на VPS
- `caddy`
- `core-api`
- `postgres`
- `lead-bot`

## Cron-задачи
- Публикация новостей каждые 5 минут (`cron_news_publish.sh`, с `flock`).
- Генерация новостей ночью (`cron_news_generate.sh`).
- Healthcheck API каждые 5 минут.
- Мониторинг диска каждые 15 минут.
- Сброс stale контрактных задач каждые 10 минут.
- Очистка idempotency-ключей раз в сутки.

## Поток данных
1. Telegram/сайт отправляют лиды в `core-api`.
2. `core-api` сохраняет лиды/события в Postgres.
3. `news.generate` читает control plane, строит контент-план (форматы/CTA/слоты) и создаёт `scheduled_posts`.
4. `news.publish` читает control plane, claim'ит записи и публикует в Telegram.
5. `news.admin_bot` позволяет включать/выключать автоматизации из Telegram (для разрешённых admin ID).
6. `contract-worker` claim'ит `contract_jobs`, анализирует, отправляет результат.

## Ключевые API-endpoints
- `GET /health` — быстрый liveness для Caddy/Docker/monitoring (вне version prefix).
- `GET /health/detailed` — расширенный health для админов (вне version prefix).
- `GET /api/v1/workers/status` — статус воркеров (`any_active`, список `workers`) для scope `worker|admin`.
- `POST /api/v1/contract-jobs/claim` — атомарный claim одной задачи worker'ом.
- `POST /api/v1/scheduled-posts/claim?limit=10` — атомарный claim пачки постов паблишером.

## Надёжность
- Idempotency для `POST /api/v1/leads` и `POST /api/v1/events`.
- Claim-паттерн через `FOR UPDATE SKIP LOCKED`:
  - `POST /api/v1/contract-jobs/claim`
  - `POST /api/v1/scheduled-posts/claim`
- Для `scheduled_posts` поддерживается retry `failed` (с cooldown) и reset stale `publishing`.
- `news.generate` применяет антидублирование: по `source_url/source_hash` и по семантической похожести текста.
- Генерация контента проходит quality-gate (обязательные секции и фактура); при провале используется fallback-шаблон.
- Контент-стратегия автоматизирована: матрица тем, форматная сетка (`signal/standard/deep/digest`) и CTA-модель.
- Любую автоматизацию можно выключить runtime через `/api/v1/automation-controls`.
- JSON-логирование во всех Python-сервисах.
- Telegram-алерты для проблем healthcheck и 500 ошибок Core API.

## Безопасность
- Scoped API keys: `bot`, `news`, `worker`, `admin`.
- Ключи хранятся только в виде bcrypt-хэшей.
- Админ-действия пишутся в `audit_log`.
- `DELETE /api/v1/leads/{id}` поддерживает удаление персональных данных.

## pgvector
- Подготовлен отдельной миграцией (`20260225_0002_pgvector.py`).
- По умолчанию не применяется в production на старте.
