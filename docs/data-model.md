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
