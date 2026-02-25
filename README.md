# legal-ai-platform

Монорепозиторий платформы лидогенерации Legal AI.

## Компоненты
- `apps/core-api` — единый backend (FastAPI + Postgres)
- `apps/lead-bot` — Telegram-бот захвата лидов
- `apps/news` — генератор и паблишер новостей
- `apps/contract-worker` — воркер анализа договоров (MacBook)
- `apps/web` — сайт
- `packages/shared` — общие схемы/типы

## Быстрый старт (dev)
```bash
uv sync
docker compose -f infra/compose/docker-compose.dev.yml up --build
```

## Полезные команды
```bash
make lint
make test
make dev
make prod
make deploy
make integration-test
```
