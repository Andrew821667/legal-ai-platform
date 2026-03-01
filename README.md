# legal-ai-platform

Монорепозиторий платформы лидогенерации Legal AI.

## Компоненты
- `apps/core-api` — единый backend (FastAPI + Postgres)
- `apps/lead-bot` — Telegram-бот захвата лидов
- `apps/news` — генератор, паблишер и admin-бот новостей
- `apps/news/legacy` — reader-бот канала (персонализация/поиск/сохранённое)
- `apps/contract-worker` — воркер анализа договоров (MacBook)
- `apps/web` — сайт
- `packages/shared` — общие схемы/типы

## Быстрый старт (dev)
```bash
uv sync
docker compose -f infra/compose/docker-compose.dev.yml up --build
```

Важно:
- после любого изменения Python-зависимостей в workspace-пакетах нужно регенерировать корневой `uv.lock` командой `uv lock`;
- для `apps/lead-bot` это критично: `python-telegram-bot[job-queue]` ставится через `apps/lead-bot/pyproject.toml`, а не через legacy `requirements.txt`;
- production-deploy не пересобирает `lead-bot` автоматически, потому что в `infra/compose/docker-compose.prod.yml` используется готовый образ `LEAD_BOT_IMAGE`.

## Полезные команды
```bash
make lint
make test
make dev
make prod
make deploy
make integration-test
```
