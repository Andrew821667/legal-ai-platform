# Сбои и восстановление

## Core API недоступен
Симптомы:
- `lead-bot` не может отправить лиды.
- Healthcheck падает.

Авто-реакция:
- `lead-bot` пишет лиды в локальный SQLite buffer.

Ручное восстановление:
1. Проверить `docker compose ps`.
2. Проверить `core-api` логи.
3. Проверить доступность Postgres.
4. После восстановления убедиться, что буфер бота очищается.

## Postgres недоступен
Симптомы:
- `core-api` отдаёт 5xx.
- `/health/detailed` показывает `db_ok=false`.

Ручное восстановление:
1. Проверить контейнер `postgres`.
2. Проверить место на диске.
3. При необходимости восстановить из бэкапа `restore_postgres.sh`.

## Telegram rate-limit / ошибки публикации
Симптомы:
- `news.publish` фиксирует 3 ошибки подряд.

Авто-реакция:
- Circuit breaker останавливает текущий прогон.
- `news.publish` переводит пост в `failed`, а `claim` берёт его повторно после cooldown (по `NEWS_RETRY_FAILED_AFTER_MINUTES`).
- При `HTTP 200` с `ok=false` от Telegram публикация также считается ошибкой и уходит в retry-цикл.

Ручное восстановление:
1. Проверить токен/права бота в канале.
2. Проверить задержки и лимиты Telegram.
3. Проверить, что `attempts < max_attempts`, и дождаться следующего cron-цикла.

## Низкое качество/повторы контента
Симптомы:
- Посты слишком похожи друг на друга или содержат общие фразы без фактов.

Авто-реакция:
- `news.generate` отбрасывает семантически похожие материалы (`NEWS_SIMILARITY_THRESHOLD`).
- Если LLM возвращает «сырой» ответ, генератор использует fallback-шаблон с обязательной структурой.

Ручное восстановление:
1. Уточнить список источников в `NEWS_SOURCE_URLS`.
2. Поднять/опустить `NEWS_SIMILARITY_THRESHOLD` (типично 0.42-0.58).
3. Задать приоритетные домены в `NEWS_PRIORITY_DOMAINS`.

## Экстренная остановка любой автоматизации
Симптомы:
- Нужно мгновенно остановить генерацию/публикацию/автоклейм без редеплоя.

Действие:
1. Через админ-панель открыть вкладку `Automation Control`.
2. Выключить нужный флаг (`news.generate.enabled`, `news.publish.enabled`, и т.д.).
3. Проверить логи соответствующего сервиса: он должен завершить цикл с сообщением `disabled_by_control_plane`.

Альтернатива:
- Через Telegram `news.admin_bot` выполнить выключение в чате (`/admin`).

## Недоступна Telegram админ-панель news.admin_bot
Симптомы:
- Бот не отвечает на `/admin`.

Проверка:
1. Убедиться, что запущен процесс `python -m news.admin_bot`.
2. Проверить `NEWS_ADMIN_BOT_TOKEN` (или fallback `TELEGRAM_BOT_TOKEN`), `API_KEY_NEWS`, `NEWS_ADMIN_IDS`.
3. Проверить доступность `GET /api/v1/automation-controls?scope=news`.

## Зависшие посты scheduled_posts
Симптомы:
- Есть записи `status=publishing`, которые не меняются длительное время.

Авто-реакция:
- `cron_reset_stale_posts.sh` переводит stale посты в `failed` (с инкрементом `attempts`) для дальнейшего retry.

Ручное восстановление:
1. Проверить логи `news.publish` и network доступ к Telegram.
2. Проверить `attempts/max_attempts` по зависшим записям.

## Worker не отвечает
Симптомы:
- Есть `contract_jobs` в `new`, но `workers/status.any_active=false`.

Авто-реакция:
- Healthcheck отправляет alert.

Ручное восстановление:
1. Проверить MacBook (сон, сеть, процесс).
2. Запустить `caffeinate -i python -m contract_worker.run`.
3. Проверить логи `/tmp/contract-worker.log`.

## Зависшие задачи contract_jobs
Симптомы:
- `status=processing` слишком долго.

Авто-реакция:
- `cron_reset_stale_jobs.sh` возвращает stale jobs в `new`.

Ручное восстановление:
1. Проверить число попыток `attempts/max_attempts`.
2. Диагностировать причину падений worker.
3. Проверить алерт по порогу `CONTRACT_STALE_PROCESSING_ALERT_THRESHOLD`.

## Накопились `new` задачи с исчерпанными попытками
Симптомы:
- в `summary` видно `new_exhausted_count > 0`;
- `claim` их не забирает (ожидаемое поведение).

Авто-реакция:
- `cron_contract_jobs_maintenance.sh` переводит такие задачи в `failed` в рамках регулярного обслуживания очереди.

Ручное восстановление:
1. Проверить через dry-run:
   `POST /api/v1/contract-jobs/finalize-exhausted-new?dry_run=true`.
2. Применить финализацию:
   `POST /api/v1/contract-jobs/finalize-exhausted-new`.
3. При необходимости вернуть конкретную задачу в `new` вручную:
   `POST /api/v1/contract-jobs/{job_id}/requeue?force=true`.

## Накопились retryable `failed` задачи
Симптомы:
- в `summary` видно `failed_retryable_count > 0`;
- срабатывает алерт по `CONTRACT_FAILED_RETRYABLE_ALERT_THRESHOLD`.

Ручное восстановление:
1. Проверить dry-run:
   `POST /api/v1/contract-jobs/retry-failed?retryable_only=true&dry_run=true`.
2. Применить retry:
   `POST /api/v1/contract-jobs/retry-failed?retryable_only=true`.

## Переполнение диска
Симптомы:
- `disk_monitor.sh` отправляет alert > 85%.

Ручное восстановление:
1. Очистить старые бэкапы/логи.
2. Проверить logrotate.
3. Увеличить SSD у провайдера.
