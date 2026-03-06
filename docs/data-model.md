# Модель данных

## Таблицы
- `api_keys` — ключи API, scope, активность, last_used.
- `users` — пользователи/операторы платформы.
- `leads` — лиды и их статус в воронке.
- `events` — события по лидам и действиям.
- `scheduled_posts` — отложенные/опубликованные посты канала.
- `contract_jobs` — очередь задач анализа договоров.
- `worker_heartbeats` — живые воркеры и их состояние.
- `idempotency_keys` — кеш ответов на повторные POST-запросы.
- `audit_log` — журнал чувствительных действий.

## Ключевые индексы
- `ix_leads_last_activity_at`
- `ix_leads_telegram_user_id` (partial)
- `ix_leads_status`
- `ix_events_lead_id` (partial)
- `ix_events_created_at`
- `ix_scheduled_posts_publish` (partial)
- `ix_scheduled_posts_source_hash` (unique, partial)
- `ix_contract_jobs_queue` (partial)
- `ix_contract_jobs_stale` (partial)
- `ix_idempotency_keys_created`
- `ix_audit_log_created`
- `ix_audit_log_target`

## Очереди
- Claim выполняется отдельными endpoint’ами:
  - `POST /api/v1/scheduled-posts/claim`
  - `POST /api/v1/contract-jobs/claim`
- Пустая очередь: `204 No Content`.
- Для polling статуса контракта используется:
  - `GET /api/v1/contract-jobs/{job_id}`
- Для операторских списков поддерживаются фильтры:
  - `GET /api/v1/contract-jobs?status=...&lead_id=...&worker_id=...`
  - `offset`, `limit`, `order_by=priority|created_at|updated_at|deadline_at`, `order_dir=asc|desc`
  - SLA-фильтры: `stale_processing_only`, `stale_minutes`, `failed_retryable_only`, `new_retryable_only`, `new_older_than_minutes`
- Для мониторинга очереди и диагностики задачи:
  - `GET /api/v1/contract-jobs/summary`
  - `GET /api/v1/contract-jobs/ops-overview`
  - `GET /api/v1/contract-jobs/{job_id}/history`
- Для keepalive активной обработки:
  - `POST /api/v1/contract-jobs/{job_id}/touch`
- Для единичного запуска обслуживания очереди:
  - `POST /api/v1/contract-jobs/maintenance?dry_run=true&retry_failed=true`
  - `POST /api/v1/contract-jobs/maintenance?dry_run=false&retry_failed=true`
- Для безопасного массового ретрая:
  - `POST /api/v1/contract-jobs/retry-failed?retryable_only=true&dry_run=true`
  - `POST /api/v1/contract-jobs/retry-failed?retryable_only=true&limit=100`
- Для очистки очереди от исчерпанных `new` задач:
  - `POST /api/v1/contract-jobs/finalize-exhausted-new?dry_run=true`
  - `POST /api/v1/contract-jobs/finalize-exhausted-new?limit=200`
- Для ручного восстановления конкретной задачи:
  - `POST /api/v1/contract-jobs/{job_id}/requeue`
  - `POST /api/v1/contract-jobs/{job_id}/requeue?force=true` (для terminal failed/done)

Поведение очереди:
- `claim` выбирает только `new` задачи с `attempts < max_attempts`.
- `reset-stale` для `processing` задач:
  - возвращает в `new`, пока лимит попыток не исчерпан;
  - переводит в terminal `failed`, если `max_attempts` достигнут.
- `finalize-exhausted-new` переводит зависшие `new` задачи с исчерпанными попытками в `failed`.

## `contract_jobs.result_json` (текущий формат от contract-worker)
- `summary` — сводка анализа.
- `risk_level` — `low|medium|high`.
- `risk_score` — балл `0..100`.
- `word_count` — число слов документа.
- `risk_hits_total` — общее число срабатываний риск-маркеров.
- `risk_counts` — частоты по маркерам.
- `risks` — уникальные найденные маркеры.
- `risk_snippets` — контекстные фрагменты вокруг срабатываний.
- `top_words` — частотный словарь.

Детально алгоритм описан в [docs/contract-analyzer.md](./contract-analyzer.md).
