# Runbook (эксплуатация)

## Локальная разработка
```bash
cp .env.example .env
uv sync
make dev
```

Проверка:
```bash
curl http://localhost:8000/health
```

## Первый запуск на production
1. Развернуть `.env`.
2. Поднять сервисы:
```bash
make prod
```
3. Применить миграции и создать первый admin-key:
```bash
docker compose -f infra/compose/docker-compose.prod.yml run --rm core-api bash -lc "cd /app/apps/core-api && alembic upgrade head"
docker compose -f infra/compose/docker-compose.prod.yml run --rm core-api python -m core_api.cli create-admin-key --name "initial-admin"
```

## Zero-downtime deploy
```bash
make deploy
```
Скрипт:
- ждёт готовность Postgres,
- применяет миграции,
- идемпотентно проверяет admin key,
- перезапускает только изменившиеся сервисы.

## Ночные и периодические задачи (cron)
Пример crontab:
```cron
30 23 * * * /opt/legal-ai/infra/scripts/cron_news_generate.sh >> /var/log/news-gen.log 2>&1
*/5 * * * * /opt/legal-ai/infra/scripts/cron_news_publish.sh >> /var/log/news-pub.log 2>&1
*/10 * * * * /opt/legal-ai/infra/scripts/cron_reset_stale_posts.sh >> /var/log/stale-posts.log 2>&1
*/5 * * * * /opt/legal-ai/infra/scripts/healthcheck.sh >> /var/log/healthcheck.log 2>&1
*/10 * * * * /opt/legal-ai/infra/scripts/cron_reset_stale_jobs.sh >> /var/log/stale-jobs.log 2>&1
*/15 * * * * /opt/legal-ai/infra/scripts/disk_monitor.sh
0 3 * * * /opt/legal-ai/infra/scripts/backup_postgres.sh >> /var/log/backup.log 2>&1
0 4 * * * /opt/legal-ai/infra/scripts/cron_cleanup_idempotency.sh >> /var/log/cleanup.log 2>&1
```

Ручная проверка генерации без записи в БД:
```bash
uv run --package news python -m news.generate --dry-run --limit 5
```

Запуск Telegram админ-панели контент-бота:
```bash
uv run --package news python -m news.admin_bot
```

Рекомендуется запускать как отдельный daemon/service (не через cron).
Для одновременной работы с лид-ботом задайте отдельный токен `NEWS_ADMIN_BOT_TOKEN`
(иначе оба процесса будут конфликтовать по long polling одного Telegram-бота).
Если `NEWS_ADMIN_BOT_TOKEN` не задан, будет использован fallback `TELEGRAM_BOT_TOKEN`.

## Control Plane автоматизаций
Просмотр активных тумблеров:
```bash
curl -s "$CORE_API_URL/api/v1/automation-controls?scope=news" -H "X-API-Key: $API_KEY_ADMIN"
```

Отключить автогенерацию контента:
```bash
curl -s -X PUT "$CORE_API_URL/api/v1/automation-controls/news.generate.enabled" \
  -H "X-API-Key: $API_KEY_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"enabled":false}'
```

Включить обратно:
```bash
curl -s -X PUT "$CORE_API_URL/api/v1/automation-controls/news.generate.enabled" \
  -H "X-API-Key: $API_KEY_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"enabled":true}'
```

Через Telegram admin-bot:
- `/admin` или `/controls` — открыть панель;
- `Статус очереди` — оперативный статус draft/scheduled/failed;
- `Включить всё/Отключить всё` — массовое управление news-автоматизациями.

## Backup/Restore
Бэкап:
```bash
./infra/scripts/backup_postgres.sh
```
Восстановление:
```bash
./infra/scripts/restore_postgres.sh /path/to/legal_ai_YYYYMMDD_HHMMSS.dump
```

## Ротация API-ключей
- Создать ключ: `POST /api/v1/admin/api-keys`
- Отозвать ключ: `DELETE /api/v1/admin/api-keys/{id}`
- Все операции логируются в `audit_log`.

## MacBook Protocol (contract-worker)
1. Установить зависимости:
```bash
uv sync
```
2. Запустить воркер без сна:
```bash
caffeinate -i uv run --package contract-worker python -m contract_worker.run
```
3. Автозапуск через `launchd` (plist в `~/Library/LaunchAgents`).
4. Логи: `/tmp/contract-worker.log`, `/tmp/contract-worker-err.log`.

Если MacBook оффлайн:
- Контрактные задачи остаются в `new`.
- Healthcheck пришлёт alert при отсутствии heartbeat.

## Troubleshooting
- Ошибки Telegram: проверить токен и права бота.
- Core API 500: проверить логи и `/health/detailed`.
- Бот буферизует лиды: проверить файл SQLite и доступность Core API.
- Нет worker heartbeat: проверить процесс на MacBook и сеть.
- Проверить живость worker'ов API-методом: `GET /api/v1/workers/status`.
