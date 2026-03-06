# Roadmap исполнения (Q1 2026)

Документ фиксирует рабочий план реализации и контрольные точки для релизов по фазам.

## Фазы и релизы

### Phase 1: `phase-1/mvp-core` (backend-only)
Цель:
- стабилизировать core-контракты, health, claim-механику и control plane.

Результат фазы:
- `core-api + postgres + caddy` готовы к стабильной эксплуатации;
- news/worker сервисы работают через claim endpoints;
- критичные операции покрыты smoke/pytest.

Критерии готовности:
- `GET /health` и `GET /health/detailed` стабильно отвечают;
- `POST /api/v1/contract-jobs/claim` и `POST /api/v1/scheduled-posts/claim` работают идемпотентно в конкурентном сценарии;
- `GET /api/v1/workers/status` возвращает `{any_active, workers}`;
- control plane переключает автоматизации без redeploy.

### Phase 2: `phase-2/clients`
Цель:
- развить клиентские контуры (в первую очередь Telegram UX контент- и лид-ботов).

Результат фазы:
- мастер создания постов: визуал -> текст -> драфт -> редактура -> публикация;
- лид-бот с квалификацией и lead scoring;
- продвинутая админ-панель бота 2 с тумблерами автоматизаций.

Критерии готовности:
- редактор выполняет полный цикл поста из Telegram без SQL/CLI;
- лид формируется структурированно и передаётся на следующий шаг продаж.

### Phase 3: `phase-3/polish`
Цель:
- стабилизация, наблюдаемость, финальная шлифовка UX и релизный hardening.

Результат фазы:
- runbook, backup/restore drill, regression и метрики качества;
- снижение операционных инцидентов и ручных вмешательств.

Критерии готовности:
- нет открытых багов P0/P1;
- rollout/rollback процедуры проверены.

## Детальный backlog: Phase 1 (день-за-днём)

### День 1: API-контракты и документация
- [x] Зафиксировать claim-подход через отдельные POST endpoints.
- [x] Зафиксировать health endpoints вне version prefix.
- [x] Зафиксировать `GET /api/v1/workers/status` в архитектурной доке.
- [x] Привести env-имена алертов к `ALERT_BOT_TOKEN` и `ALERT_CHAT_ID`.

### День 2: Миграции и модель данных
- [x] Проверить корректность всех alembic-миграций на чистой БД.
- [x] Проверить bootstrap `automation_controls`.
- [x] Убедиться, что уникальные/служебные индексы покрывают claim-сценарии.

### День 3: Конкурентность и failover
- [x] Прогнать конкурентный claim для posts/jobs (параллельные воркеры).
- [x] Проверить retry/cooldown для failed posts.
- [x] Проверить reset stale (`publishing` / `processing`) через cron-скрипты.

### День 4: Security и эксплуатация
- [x] Проверить scoped API keys (`bot/news/worker/admin`) и audit-лог.
- [x] Проверить публичную доступность `/health/detailed` как инфраструктурного endpoint.
- [x] Проверить Telegram-alert на обработчике 500.

### День 5: Тесты и release gate
- [x] Прогнать `pytest` по `apps/core-api`.
- [x] Прогнать smoke сценарий generate/publish/claim локально.
- [x] Сформировать чеклист release-gate (`docs/release-gate-phase1.md`).

## Scope-контур по договорам (чтобы не дублировать системы)
- `apps/contract-ai` не является частью текущего production-контура.
- На данном этапе реализуется только endpoint-слой и очередь задач в `core-api` + исполнение воркером `apps/contract-worker` (MacBook).
- Полноценная интеграция `contract-ai` рассматривается отдельной фазой после стабилизации текущего ядра.

## Правила релизов
- Ветка на фазу -> PR в `main` -> CI -> deploy на VPS.
- Деплой только после прохождения release gate текущей фазы.
- Любая автоматизация должна отключаться runtime через control plane.
