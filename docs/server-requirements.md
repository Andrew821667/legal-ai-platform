# Требования к серверу

## Минимальный старт
- 2 vCPU
- 4 GB RAM
- 40 GB SSD
- Swap: 2 GB (рекомендуется)

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

## Рост
- Вертикально: увеличить RAM/SSD на текущем VPS.
- Горизонтально:
  - VPS A: `core-api + postgres + bots`
  - MacBook/VPS B: `contract-worker` и тяжёлые джобы генерации.

## Ограничения
- На VPS запрещены always-on локальные ML модели (`torch/transformers`).
- Паблишер новостей работает только как cron-задача.
- Медиафайлы не храним на VPS-диске: используем `tg://file_id` или внешние URL.
