# Требования к серверу

## Минимальный старт
- 2 vCPU
- 4 GB RAM
- 40 GB SSD
- Swap: 2 GB (рекомендуется)

Режим запуска для `2/4`:
- always-on: `postgres`, `core-api`, `lead-bot`, `news-admin-bot`, `news-reader-bot`, `news-publish`, `caddy` (и `web` при необходимости);
- slot-heavy: `news-telegram-ingest`, `news-generate`, `news-reader-digest`;
- `contract-worker` на локальном ноутбуке (VPS хранит очередь и статусы).

## Оценка RAM
| Сервис | RAM |
|---|---|
| ОС + system services | ~300 MB |
| Postgres (тюнинг) | 400-600 MB |
| Core API (1 worker) | 100-150 MB |
| Lead Bot | 80-120 MB |
| Caddy | ~30 MB |
| Cron задачи (пик) | 100-200 MB |
| Итого | ~1.0-1.3 GB |

## Тюнинг пула БД (core-api)
Рекомендуемые значения для VPS `2 vCPU / 4 GB`:
- `DB_POOL_SIZE=8`
- `DB_MAX_OVERFLOW=8`
- `DB_POOL_TIMEOUT_SECONDS=30`
- `DB_POOL_RECYCLE_SECONDS=1800`

Примечание:
- для `sqlite` эти параметры не применяются (используется отдельный путь подключения).

## Рост
- Вертикально: увеличить RAM/SSD на текущем VPS.
- Горизонтально:
  - VPS A: `core-api + postgres + bots`
  - MacBook/VPS B: `contract-worker` и тяжёлые джобы генерации.

## Ограничения
- На VPS запрещены always-on локальные ML модели (`torch/transformers`).
- Паблишер новостей работает loop-сервисом, а не cron-задачей.
- Медиафайлы не храним на VPS-диске: используем `tg://file_id` или внешние URL.
- В слотных воркерах должен быть включен контроль наложения через `busy` heartbeat и `slot_grace_minutes`.
