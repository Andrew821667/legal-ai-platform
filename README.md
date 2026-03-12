# legal-ai-platform

Монорепозиторий платформы лидогенерации Legal AI.

## Компоненты
- `apps/core-api` — единый backend (FastAPI + Postgres), включая контуры лидов, contract jobs и `special paid consultation` orders/payments
- `apps/lead-bot` — Telegram-бот захвата лидов
- `apps/news` — генератор, паблишер и admin-бот новостей
- `apps/news/legacy` — reader-бот канала (персонализация/поиск/сохранённое)
- `apps/contract-worker` — воркер анализа договоров (MacBook)
- `apps/contract-ai` — локальный reference-контур; реальный `Contract_AI_System` ведется отдельно в `https://github.com/Andrew821667/Contract-AI-System-` и не является частью текущего production pipeline этого монорепо
- `apps/web` — сайт
- `packages/shared` — общие схемы/типы

Документация по анализу договоров:
- `docs/contract-analyzer.md` — алгоритм и формат результата `contract-worker`.

## Быстрый старт (dev)
```bash
uv sync
docker compose -f infra/compose/docker-compose.dev.yml up --build
```

Важно:
- после любого изменения Python-зависимостей в workspace-пакетах нужно регенерировать корневой `uv.lock` командой `uv lock`;
- для `apps/lead-bot` это критично: `python-telegram-bot[job-queue]` ставится через `apps/lead-bot/pyproject.toml`, а не через legacy `requirements.txt`;
- `special paid consultation` живет в `core-api` как отдельный продуктовый слой и не заменяет бесплатную консультацию по умолчанию;
- production-deploy не пересобирает `lead-bot` автоматически, потому что в `infra/compose/docker-compose.prod.yml` используется готовый образ `LEAD_BOT_IMAGE`.
- если менялись migration/модели `apps/core-api`, сначала нужно обновить `CORE_API_IMAGE`, потом выполнить Alembic миграции, и только после этого перезапускать `lead-bot`;
- `infra/scripts/deploy.sh` теперь делает это в правильном порядке: `docker compose pull` -> `alembic upgrade head` -> restart сервисов.

## Полезные команды
```bash
make lint
make lint-full
make test
make dev
make prod
make deploy
make integration-test
```

`make lint` теперь проверяет runtime-критичные правила Ruff (ошибки, влияющие на надежность/поведение).
Полный технический аудит стиля и форматирования запускается отдельно через `make lint-full`.
