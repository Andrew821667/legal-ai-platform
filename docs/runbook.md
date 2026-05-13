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

## Локальный full-stack через docker-compose
```bash
cd "/Users/andrew/Мои AI проекты/legal-ai-platform"
CORE_API_PUBLISH_PORT=8001 \
CADDYFILE_PATH=../caddy/Caddyfile.local \
docker-compose --env-file .env -f infra/compose/docker-compose.prod.yml up -d --build
```

Примечания:
- `core-api` контейнер сам выполняет `alembic upgrade head` при старте, поэтому чистая локальная БД поднимается без отдельного ручного шага миграций.
- Для локального full-stack используйте `infra/caddy/Caddyfile.local`: он слушает только `:80` и не пытается получать боевой TLS-сертификат для `ai-verdict.ru`.
- `reader-bot` в таком запуске требует `READER_BOT_TOKEN` в корневом `.env`.
- Для отправки feedback-сигналов ридера в `core-api` также обязательны `API_KEY_NEWS` (scope `news`/`admin`) и, желательно, `READER_BOT_USERNAME` (deeplink вида `/start post_<uuid>`).

## Mac Mini: раздельные контуры пользователей

Текущая схема Mac Mini нормальна, если контуры явно разделены:
- `legalai` — публичный контур без VPN: сайт, mini-app, contract-система, Cloudflare tunnel;
- `aiwork` — bot/news контур с VPN: lead-bot, news admin, генерация, ingest, публикации, reader;
- `core-api` + `postgres` — общий источник состояния, к которому оба контура обращаются по стабильным адресам.

Критичные правила:
- не запускать `core-api` вручную через `docker run`, если можно поднять его из compose: ручной запуск теряет настройки при пересборке и усложняет диагностику;
- `CORE_API_WORKERS` задает число uvicorn worker'ов; production default в образе — `4`;
- `CORE_API_DOCKER_URL` — адрес API внутри docker-сети; unified compose подставляет его в контейнерный `CORE_API_URL`;
- `CORE_API_HOST_URL` / `CORE_API_PUBLISH_PORT` — адрес для smoke/deploy-проверок с хоста, например `http://127.0.0.1:8100`;
- контейнер `core-api` имеет сетевой alias `legal-ai-core-api`, чтобы отдельный bot-compose мог ходить к нему по одному имени в общей docker network.

Рекомендуемые env для Mac Mini:
```bash
CORE_API_WORKERS=4
CORE_API_BIND_HOST=127.0.0.1
CORE_API_PUBLISH_PORT=8100
CORE_API_DOCKER_URL=http://legal-ai-core-api:8000
CORE_API_HOST_URL=http://127.0.0.1:8100
COMPOSE_PROJECT=compose
MINIAPP_PUBLIC_BASE_URL=https://ai-verdict.ru
READER_MINIAPP_BASE_URL=https://ai-verdict.ru
```

Если bot-compose живет отдельным файлом, он должен быть подключен к той же docker network, где находится `legal-ai-core-api`, и использовать `CORE_API_URL=http://legal-ai-core-api:8000` внутри контейнеров ботов.

CI/CD:
- GitHub Actions собирает runtime-образы в GHCR: `core-api`, `web`, `lead-bot`, `news`, `news-reader`;
- на Mac Mini в `.env` должны быть заданы `CORE_API_IMAGE`, `WEB_IMAGE`, `LEAD_BOT_IMAGE`, `NEWS_IMAGE`, `NEWS_READER_IMAGE`;
- GitHub Actions передает временный `github.token` в `infra/scripts/deploy_macmini.sh`, поэтому отдельный `GHCR_TOKEN` secret не нужен;
- деплой из GitHub Actions включается только при `ENABLE_MACMINI_DEPLOY=true` и настроенных Tailscale OAuth secrets `TS_OAUTH_CLIENT_ID` и `TS_OAUTH_SECRET`;
- production-деплой использует единый compose-файл `infra/compose/docker-compose.prod.yml` в `/Users/legalai/projects/legal-ai-platform`.

Проверка после деплоя:
```bash
infra/scripts/macmini_deploy_check.sh
```

DNS/Cloudflare:
- целевая зона: `ai-verdict.ru`;
- сайт и mini-app используют base `https://ai-verdict.ru`, mini-app живет на маршрутах `/miniapp...`;
- Contract_AI_System использует тот же зарегистрированный домен через поддомен `contract.ai-verdict.ru`;
- если используется Cloudflare Tunnel, в регистраторе нужно перевести NS домена на nameservers Cloudflare и убрать конфликтующие DNSSEC/DS записи;
- если домен остается на DNS Рег.ру, нужно вручную создать записи для apex, `www` и `contract` на выбранный публичный вход; Cloudflare Tunnel без Cloudflare DNS требует отдельной CNAME/ALIAS-схемы у регистратора;
- проверка: `dig ai-verdict.ru NS +short`, `dig ai-verdict.ru A +short`, `dig www.ai-verdict.ru A +short`, `dig contract.ai-verdict.ru A +short`.

Безопасность:
- реальные значения токенов, API-ключей, DB password и tunnel token не должны попадать в git или runbook;
- если такие значения передавались в чатах/логах/скриншотах, запланировать ротацию по `docs/secret-rotation-checklist.md`.

## Contract_AI_System на локальном MacBook (Docker)

Если `Contract-AI-System` запущен отдельным Docker-контуром на этом же MacBook, в `core-api` это должно быть отражено через `automation_controls`.

Критично для Docker:
- внутри контейнеров legal-ai-platform нельзя использовать `localhost` для связи с Contract-AI-System;
- используйте `host.docker.internal:<port_contract_ai>` (или общий docker network + service name, если контуры объединены).

Базовые ключи:
- `contract_ai.enabled`
- `contract_ai.channel_gate.enabled`
- `contract_ai.quick_demo.enabled`
- `contract_ai.demo_link.enabled`
- `contract_ai.local_bridge.enabled`
- `contract_ai.reader_cta.enabled`

Рекомендуемый стартовый профиль для локального Docker-режима:
- `contract_ai.local_bridge.enabled = true`
- `contract_ai.local_bridge.config.deployment = "docker_local_macbook"`
- `contract_ai.local_bridge.config.mode = "online"` если локальный контур доступен, иначе `offline`
- `contract_ai.local_bridge.config.status_url|demo_link_url|analysis_url` — адреса bridge-эндпоинтов локального контура

Рекомендуемые env (корневой `.env`) для автоподстановки в `automation_controls`:
```bash
CONTRACT_AI_BRIDGE_ENABLED_DEFAULT=true
CONTRACT_AI_BRIDGE_DEPLOYMENT=docker_local_macbook
CONTRACT_AI_BRIDGE_MODE=online
CONTRACT_AI_BRIDGE_STATUS_URL=http://host.docker.internal:18080/health
CONTRACT_AI_BRIDGE_DEMO_LINK_URL=http://host.docker.internal:18080/api/v1/public/demo-link
CONTRACT_AI_BRIDGE_ANALYSIS_URL=http://host.docker.internal:18080/api/v1/public/analysis
```

Проверка доступности из `core-api` контейнера:
```bash
docker compose -f infra/compose/docker-compose.prod.yml exec core-api \
  python -c "import urllib.request;print(urllib.request.urlopen('http://host.docker.internal:18080/health',timeout=5).status)"
```

Важно:
- при `mode=offline` внешние контуры (site/lead-bot/reader/mini-app) не должны ломаться;
- пользователь переводится в сценарий очереди/консультации, а не получает ошибку доступа к кабинету.

## Единый smoke для всех ботов (Docker)
После обновлений по ботам запускайте единый smoke:
```bash
cd "/Users/andrew/Мои AI проекты/legal-ai-platform"
make smoke-bots
```

Что делает скрипт `infra/scripts/smoke_bots_stack.sh`:
- поднимает в compose все бот-сервисы и зависимости (`postgres`, `core-api`, `lead-bot`, `news-admin-bot`, `news-reader-bot`, `news-reader-digest`, `news-generate`, `news-telegram-ingest`, `news-publish`);
- проверяет, что polling-боты не используют один и тот же токен (`lead/admin/reader`);
- ждёт `core-api /health`, проверяет активность required worker'ов;
- выполняет `integration_test.sh`, `smoke_reader_digest.sh` и `e2e_reader_to_lead.sh`;
- проверяет логи на типовые критичные ошибки (`Unauthorized`, `Connection refused`, `NameResolutionError`, конфликт polling).

Полезные флаги:
```bash
# не поднимать заново контейнеры, только проверки
SMOKE_SKIP_UP=1 make smoke-bots

# без полного e2e reader->lead
SMOKE_RUN_E2E=0 make smoke-bots
```

## Release Gate (site + reader + mini-app)
Для формальной приемки релиза по контуру сайта, reader-бота и mini-app используйте:
- чеклист/критерии: `docs/stage-8-release-gate-site-reader-miniapp.md`;
- обязательный smoke: `make smoke-bots`;
- rollback-порядок: раздел 4 в `docs/stage-8-release-gate-site-reader-miniapp.md`.

## Первый запуск на production
1. Развернуть `.env`.
2. Поднять сервисы:
```bash
make prod
```
Будут подняты: `postgres`, `core-api`, `lead-bot`, `news-generate`, `news-telegram-ingest`, `news-publish`,
`news-admin-bot`, `news-reader-bot`, `news-reader-digest`, `web`, `caddy`.
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
- сначала тянет свежие image;
- поднимает `postgres`, если он не запущен;
- ждёт готовность Postgres,
- применяет миграции уже свежим образом `core-api`,
- идемпотентно проверяет admin key,
- перезапускает image-based сервисы,
- пересобирает build-based сервисы (`web`, `news-*`, `news-reader-bot`, `news-reader-digest`),
- затем перезапускает `caddy`.

Критичное правило для миграций `core-api`:
- если менялись Alembic migration, модели `core-api` или контракты `users/leads`, сначала нужно обновить `CORE_API_IMAGE`;
- миграции должны выполняться только свежим образом `core-api`, а не тем, который уже был на VPS;
- порядок должен быть таким: `docker compose pull` -> `alembic upgrade head` -> restart `core-api` -> restart `lead-bot` и остальных consumers;
- если сделать наоборот, `lead-bot` может стартовать на новой логике против старой схемы БД и уйти в частичный fallback на SQLite.

Критичное правило для `lead-bot`:
- production compose поднимает `lead-bot` из образа `LEAD_BOT_IMAGE`, а не через `build`;
- поэтому изменения в `apps/lead-bot/pyproject.toml` и корневом `uv.lock` не попадут на VPS одним только `make deploy`;
- если менялись зависимости лид-бота, сначала нужно пересобрать и запушить образ `lead-bot`, и только потом выполнять `make deploy`;
- частный случай: `python-telegram-bot[job-queue]` нужен для фонового scheduler'а. Если образ не пересобран, бот стартует с предупреждением `JobQueue is not available`, и отложенные уведомления по лидам будут выключены.

Минимальная проверка после деплоя лид-бота:
```bash
docker compose -f infra/compose/docker-compose.prod.yml logs --tail=50 lead-bot
```
В логах должно быть:
- `Scheduler started`
- `Added job "pending_leads_notifier"`

В логах не должно быть:
- `JobQueue is not available`

Критичное правило для `web` и `news`:
- `web`, `news-generate`, `news-telegram-ingest`, `news-publish`, `news-admin-bot`, `news-reader-bot`, `news-reader-digest` в production compose собираются из текущего checkout на сервере;
- поэтому после `git pull` нужен именно `docker compose up -d --build ...`, а не только `docker compose pull`;
- если ограничиться только `pull`, код этих сервисов на VPS не обновится.

Отдельный deploy-порядок для миграции `lead-bot legacy -> core-api`:
1. Обновить образы:
```bash
docker compose -f infra/compose/docker-compose.prod.yml pull core-api lead-bot
```
2. Применить миграции `core-api`:
```bash
docker compose -f infra/compose/docker-compose.prod.yml run --rm core-api bash -lc "cd /app/apps/core-api && alembic upgrade head"
```
3. Перезапустить `core-api`:
```bash
docker compose -f infra/compose/docker-compose.prod.yml up -d --no-deps core-api
```
4. Дождаться health:
```bash
curl -sf http://localhost:8000/health
```
5. Только после этого перезапустить `web` и `lead-bot`:
```bash
docker compose -f infra/compose/docker-compose.prod.yml up -d --build --no-deps web
docker compose -f infra/compose/docker-compose.prod.yml up -d --no-deps lead-bot
```
6. Затем пересобрать и поднять news-сервисы:
```bash
docker compose -f infra/compose/docker-compose.prod.yml up -d --build --no-deps news-generate news-telegram-ingest news-publish news-admin-bot news-reader-bot news-reader-digest
docker compose -f infra/compose/docker-compose.prod.yml up -d --no-deps caddy
```
7. Проверить логи:
```bash
docker compose -f infra/compose/docker-compose.prod.yml logs --tail=100 core-api web lead-bot news-generate news-telegram-ingest news-publish news-admin-bot news-reader-bot news-reader-digest caddy
```

Что проверить после migration `users/leads`:
- в `core-api` нет ошибок по отсутствующим колонкам `users.*` и `leads.*`;
- `lead-bot` не пишет предупреждения про fallback/ошибки синхронизации `core-api`;
- `/profile`, `/consent_status`, `/export_data`, admin user card и lead notifications работают без расхождения данных.

Локальный порядок проверки migration `users/leads`:
1. Поднять Postgres и `core-api`.
2. Применить миграции:
```bash
cd apps/core-api
../../.venv/bin/alembic upgrade head
```
3. Прогнать API-тесты:
```bash
cd /Users/andrew/Мои\ AI\ проекты/legal-ai-platform
.venv/bin/pytest apps/core-api/tests/test_leads_api.py apps/core-api/tests/test_users_api.py -q
```
4. Прогнать legacy-тесты лид-бота:
```bash
cd apps/lead-bot/legacy
../../../../legal-ai-platform/.venv/bin/pytest tests/test_database.py tests/test_imports.py tests/test_admin_interface.py -q
```
5. Перезапустить локальный `lead-bot` только после успешных миграций `core-api`.

Тонкая настройка отложенных уведомлений `lead-bot` (pending leads):
- `PENDING_LEADS_CHECK_INTERVAL_SECONDS` — частота фоновой проверки;
- `PENDING_LEADS_IDLE_MINUTES` — сколько минут тишины считать “лид готов к уведомлению”;
- `PENDING_LEADS_JOB_MAX_BATCH` — максимум лидов за один проход;
- `PENDING_LEADS_NOTIFY_TIMEOUT_SECONDS` — таймаут отправки одного уведомления;
- `PENDING_LEADS_JOB_MISFIRE_GRACE_SECONDS` — допустимый лаг scheduler без warning/misfire.

## Ночные и периодические задачи (cron)
News-пайплайн (`news-telegram-ingest`, `news-generate`, `news-publish`, `news-reader-digest`) запускается в compose в постоянных loop-процессах:
- `news-telegram-ingest` и `news-generate` реально выполняют работу только в слотах из control-plane;
- `news-publish` опрашивает очередь по интервалу `NEWS_PUBLISH_INTERVAL_SECONDS`.
- `news-reader-digest` отправляет reader-дайджесты по слоту из `news.reader_digest.enabled.config.slot_time`.
- slot-воркеры (`ingest`/`generate`/`reader-digest`) обмениваются heartbeat-полем `busy` и не запускают тяжелый цикл, пока соседний слот-воркер занят;
- для защиты от дрейфа времени и кратковременных блокировок используется `slot_grace_minutes` в control-plane (`news.generate.enabled`, `news.telegram_ingest.enabled`, `news.reader_digest.enabled`);
- `NEWS_PUBLISH_IDLE_FALLBACK_ENABLED=false` оставляет публикации строго на due-слотах. Не включайте fallback в production, иначе паблишер начнёт немедленно выпускать `ready/review`-посты при пустой due-очереди.
Чтобы не было пакетных публикаций при накопившихся due-постах, ограничивайте клейм:
`NEWS_PUBLISH_CLAIM_LIMIT=1` (или через `news.publish.enabled.config.claim_limit`).

Cron оставляем для служебных задач:
Пример crontab:
```cron
*/10 * * * * /opt/legal-ai/infra/scripts/cron_reset_stale_posts.sh >> /var/log/stale-posts.log 2>&1
*/5 * * * * /opt/legal-ai/infra/scripts/healthcheck.sh >> /var/log/healthcheck.log 2>&1
*/10 * * * * /opt/legal-ai/infra/scripts/cron_contract_jobs_maintenance.sh >> /var/log/contract-jobs-maintenance.log 2>&1
*/15 * * * * /opt/legal-ai/infra/scripts/disk_monitor.sh
0 3 * * * /opt/legal-ai/infra/scripts/backup_postgres.sh >> /var/log/backup.log 2>&1
0 4 * * * /opt/legal-ai/infra/scripts/cron_cleanup_idempotency.sh >> /var/log/cleanup.log 2>&1
```

SLA-алерты в `healthcheck.sh`:
- неактивные обязательные воркеры (`REQUIRED_NEWS_WORKERS`);
- отсутствие новых драфтов дольше порога (`DRAFT_MAX_IDLE_HOURS`);
- просроченная очередь публикации (`DUE_POSTS_ALERT_THRESHOLD`).

Доп. настройки алертов:
```bash
SLA_ALERTS_ENABLED=1
REQUIRED_NEWS_WORKERS=news-generate,news-telegram-ingest,news-publish,news-reader-digest
DRAFT_MAX_IDLE_HOURS=24
DUE_POSTS_ALERT_THRESHOLD=0
ALERT_COOLDOWN_SECONDS=1800
ALERT_STATE_FILE=/tmp/legal-ai-alert-state.json
CONTRACT_EXHAUSTED_NEW_ALERT_THRESHOLD=0
CONTRACT_STALE_PROCESSING_ALERT_THRESHOLD=0
CONTRACT_FAILED_RETRYABLE_ALERT_THRESHOLD=0
CONTRACT_MAINTENANCE_LIMIT_EACH=200
CONTRACT_MAINTENANCE_STALE_MINUTES=30
CONTRACT_MAINTENANCE_RETRY_FAILED=0
CONTRACT_MAINTENANCE_RETRY_FAILED_ONLY_RETRYABLE=1
# CONTRACT_MAINTENANCE_RETRY_FAILED_OLDER_THAN_MINUTES=60
```

Ручная проверка генерации без записи в БД:
```bash
uv run --package news python -m news.generate --dry-run --limit 5
```

Запуск Telegram админ-панели контент-бота:
```bash
uv run --package news python -m news.admin_bot
```

В production админ-бот поднимается сервисом `news-admin-bot`.
Для одновременной работы с лид-ботом задайте отдельный токен `NEWS_ADMIN_BOT_TOKEN`
(иначе оба процесса будут конфликтовать по long polling одного Telegram-бота).

Важно для feedback pipeline:
- `news-admin-bot` должен быть админом в канале публикации или иметь доступ к `message_reaction_count` updates по этому каналу;
- если комментарии идут через linked discussion group, бот должен состоять в этой группе;
- при необходимости ограничьте сбор комментариев env-переменными `NEWS_DISCUSSION_CHAT_ID` или `NEWS_DISCUSSION_CHAT_USERNAME`;
- без этого реакции/комментарии не попадут в feedback snapshot и feedback-guard не будет иметь данных для фильтрации.

Минимальные env для feedback:
```bash
TELEGRAM_CHANNEL_USERNAME=@ai_verdict
NEWS_DISCUSSION_CHAT_ID=-100...
# или NEWS_DISCUSSION_CHAT_USERNAME=...
```

Важно для Telegram parser worker:
- парсер запускается отдельным сервисом `news-telegram-ingest` и отправляет heartbeat как `news-telegram-ingest`;
- его слоты задаются отдельно от генератора через control key `news.telegram_ingest.enabled` (`morning_time`, `evening_time`, `fetch_limit`);
- в Docker рекомендуется хранить Telethon-сессию и кэш в общем `/app/data`:
  - `TELEGRAM_SESSION_NAME_DOCKER=/app/data/telegram_bot`
  - `NEWS_TELEGRAM_CACHE_PATH=/app/data/news_telegram_cache.json`

Reader digest worker:
- отдельный сервис `news-reader-digest`, heartbeat id: `news-reader-digest`;
- control key: `news.reader_digest.enabled`;
- основные config-поля:
  - `slot_time` — время авторассылки digest;
  - `max_users_per_cycle` — лимит пользователей за один проход;
  - `run_once_token` — ручной one-shot прогон (устанавливается из админ-бота кнопкой «Тестовый прогон»).
- проверка активности:
```bash
curl -s "$CORE_API_URL/api/v1/workers/news-reader-digest/activity?hours=24&limit=20" -H "X-API-Key: $API_KEY_ADMIN"
```
- быстрый smoke-check контура:
```bash
CORE_API_URL=http://localhost:8000 API_KEY_ADMIN=... infra/scripts/smoke_reader_digest.sh
```

Единый словарь event-метрик (`web` + `mini-app` + `reader-bot`):
- `source` хранится в dot-формате (`miniapp.home`, `miniapp.content`, `reader.nav`, `reader.article.card` и т.д.);
- `action` хранится в каноническом словаре (`open.content`, `open.contract_ai`, `flow.discover`, `profile.saved`, `open.miniapp.*`);
- `event_type` хранится в ограниченном наборе (`action`, `nav_click`, `cta_click`, `content_open`, `tool_open`, `solution_open`, `profile_saved`, `deeplink_open`, `deeplink_issued`);
- `core-api` дополнительно нормализует legacy-значения (`miniapp_home`, `reader_nav_open_miniapp_content`, `open_saved` и т.п.), чтобы аналитика конверсии оставалась сквозной даже при старых клиентах.

Кастомные иконки кнопок Telegram:
- Bot API поддерживает `icon_custom_emoji_id` для `KeyboardButton` и `InlineKeyboardButton`, но для показа нужны реальные document ID кастомных emoji;
- в проекте для этого предусмотрены env-переменные:
  - `NEWS_ADMIN_BUTTON_ICON_MAP`
  - `LEAD_BOT_BUTTON_ICON_MAP`
  - `NEWS_READER_BUTTON_ICON_MAP`
- формат значения: `semantic_key=document_id,semantic_key=document_id`
- рекомендуемый набор для текущего проекта:
```bash
NEWS_ADMIN_BUTTON_ICON_MAP=panel=5312486108309757006,create=5373251851074415873,sections=5357315181649076022,calendar=5433614043006903194,review=5357121491508928442,drafts=5373251851074415873,ready=5418085807791545980,posted=5309984423003823246,failed=5379748062124056162,queue=5434144690511290129,automation=5312016608254762256,summary=5350305691942788490,workers=5350554349074391003,help=5377316857231450742,publish=5309984423003823246,save=5373251851074415873
LEAD_BOT_BUTTON_ICON_MAP=services=5357315181649076022,consultation=5312536423851630001,contact=5409357944619802453,profile=5357107601584693888,documents=5350481781306958339,personal=5310029292527164639,admin=5350554349074391003,restart=5408906741125490282,help=5377316857231450742,send_phone=5409357944619802453,telegram=5348436127038579546,consent_accept=5312138559556164615,consent_decline=5379748062124056162,policy=5350481781306958339,return_bot=5312486108309757006
NEWS_READER_BUTTON_ICON_MAP=read_more=5309965701241379366,useful=5312536423851630001,not_interesting=5379748062124056162,digest_accept=5434144690511290129,digest_decline=5379748062124056162,save=5357315181649076022,digest=5434144690511290129,search=5309965701241379366,publish=5309984423003823246,create=5373251851074415873,share=5309984423003823246,question=5377316857231450742,idea=5312536423851630001
```
- после изменения этих env нужно перезапустить соответствующий бот.

Проверка после запуска `news-admin-bot`:
- в логах не должно быть постоянных `news_feedback_*_failed`;
- после реакции/комментария под опубликованным постом в `scheduled_posts.feedback_snapshot` должны появляться поля `reaction_total`, `comments_total`, `score`.

Запуск reader-бота (локально):
```bash
cd apps/news/legacy
python -u -m app.reader_bot
```

Важно для reader-bot sync с core-api:
- для единого контура (`/api/v1/reader/preferences`, `/api/v1/reader/feed`, `/api/v1/reader/saved`, `/api/v1/reader/save`, `/api/v1/reader/lead-intent`) должны быть заданы `CORE_API_URL` и `API_KEY_NEWS`;
- при недоступности core-api reader-bot уходит в fallback на локальные таблицы и продолжает отвечать, но кросс-бот аналитика и lead-intent в core-api не записываются.
- для стабильной работы на слабом VPS задайте параметры bridge-клиента (опционально):
  - `CORE_API_CONNECT_TIMEOUT_SECONDS=2.5`
  - `CORE_API_READ_TIMEOUT_SECONDS=8`
  - `CORE_API_FAIL_FAST_SECONDS=10`
  - `CORE_API_READ_CACHE_TTL_SECONDS=20`
  - `CORE_API_READ_CACHE_STALE_SECONDS=180`
  - `CORE_API_POOL_CONNECTIONS=20`
  - `CORE_API_POOL_MAXSIZE=50`
- для web mini-app proxy также задайте таймаут upstream:
  - `CORE_API_FETCH_TIMEOUT_MS=7000`
- для web mini-app proxy read-cache/stale fallback (снижение нагрузки и graceful degradation):
  - `CORE_API_READ_CACHE_TTL_MS=10000`
  - `CORE_API_READ_CACHE_STALE_MS=120000`
- чтобы разделы `Проверить/Решения` открывали корректные маршруты, при необходимости задайте:
  - `READER_CONTRACT_AI_URL` (по умолчанию `https://contract.ai-verdict.ru`);
  - `READER_FOR_LAWYERS_URL` (по умолчанию `https://ai-verdict.ru/for-lawyers`);
  - `READER_FOR_BUSINESS_URL` (по умолчанию `https://ai-verdict.ru/for-business`).

Разделение доменов (рекомендуется):
- `ai-verdict.ru` — основной сайт платформы;
- `contract.ai-verdict.ru` — отдельный контур Contract_AI_System.

Для `caddy` в `docker-compose.prod.yml` предусмотрены env:
- `CONTRACT_DOMAIN` (по умолчанию `contract.ai-verdict.ru`);
- `CONTRACT_AI_UPSTREAM` (по умолчанию `host.docker.internal:3000`).

Перед запуском убедитесь, что у DNS есть запись `A/AAAA` для `contract.ai-verdict.ru`, а upstream доступен из контейнера `caddy`.
- доступные deep-link payload для `https://t.me/<reader_bot>?start=<payload>`:
  - `discover`, `validate`, `solutions`, `profile`, `search`;
  - `miniapp_content`, `miniapp_tools`, `miniapp_solutions`, `miniapp_profile`.
- для сквозной персонализации mini-app/reader используется endpoint
  `/api/v1/reader/continue-state` (recommended section/screen + saved/events/lead-intent counters).
- для сквозной конверсии reader/mini-app используется endpoint
  `/api/v1/reader/conversion-funnel?hours=168` (воронка + top `source/action` + разбивка по `cta_variant`).
- A/B-раскладка CTA для reader/mini-app управляется control key
  `news.reader_cta_ab.enabled` (`seed`, `enabled_variants`, `split`).
- для ускорения аналитики используется rollup-таблица `reader_event_rollups`;
  если миграция еще не применена, API продолжит работать по raw-событиям (с меньшей производительностью).

Запуск reader digest-воркера (локально):
```bash
cd apps/news/legacy
python -u -m app.reader_digest_loop
```

E2E smoke `reader -> lead` (API-контур):
```bash
CORE_API_URL=http://localhost:8000 API_KEY_ADMIN=... E2E_TEST_USER_ID=321681061 \
infra/scripts/e2e_reader_to_lead.sh
```

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
- `/posts` — вкладки постов (`draft`/`scheduled`/`failed`) с ручной публикацией и редактированием (manual/LLM);
- в карточке поста доступны быстрые слоты перепланирования (`+1ч`, `19:00`, `завтра 10:00`);
- в карточке поста виден `feedback snapshot` по реакциям и комментариям;
- для `draft/failed` доступно пакетное действие «В готовые (все на странице)».
- ручная публикация теперь идёт через confirm-step (кнопка подтверждения перед отправкой в канал).
- `Включить всё/Отключить всё` — массовое управление news-автоматизациями.
- отдельные тумблеры `news.feedback.collect.enabled` и `news.feedback.guard.enabled` отвечают за автоматический сбор сигналов и фильтрацию новых публикаций по слабой реакции аудитории.

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
Граница контура:
- текущий production-контур договоров = `core-api` + `contract-worker`;
- `apps/contract-ai` не подключён к runtime-контуру и не запускается в основном compose.
- Логика анализатора и формат `result_json`: [docs/contract-analyzer.md](./contract-analyzer.md).

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
5. Рекомендованная настройка keepalive активной задачи:
```bash
JOB_TOUCH_INTERVAL_SECONDS=30
```

Быстрые API-проверки по контрактной очереди:
```bash
curl -s "$CORE_API_URL/api/v1/contract-jobs/summary?window_hours=24&stale_minutes=30" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s "$CORE_API_URL/api/v1/contract-jobs/ops-overview?window_hours=24&stale_minutes=30&sample_limit=10&events_limit=30" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s -X POST "$CORE_API_URL/api/v1/contract-jobs/maintenance?dry_run=true&retry_failed=true&limit_each=200&stale_minutes=30" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s "$CORE_API_URL/api/v1/contract-jobs/{job_id}/history?limit=20" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s "$CORE_API_URL/api/v1/contract-jobs?stale_processing_only=true&stale_minutes=30&limit=50" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s "$CORE_API_URL/api/v1/contract-jobs?failed_retryable_only=true&order_by=updated_at&order_dir=asc&limit=50" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s "$CORE_API_URL/api/v1/contract-jobs?new_retryable_only=true&order_by=priority&order_dir=asc&limit=50" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s -X POST "$CORE_API_URL/api/v1/contract-jobs/retry-failed?retryable_only=true&dry_run=true&limit=100" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s -X POST "$CORE_API_URL/api/v1/contract-jobs/retry-failed?retryable_only=true&limit=100" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s -X POST "$CORE_API_URL/api/v1/contract-jobs/{job_id}/requeue?reason=manual_requeue" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s -X POST "$CORE_API_URL/api/v1/contract-jobs/{job_id}/requeue?force=true&reason=force_requeue" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s -X POST "$CORE_API_URL/api/v1/contract-jobs/finalize-exhausted-new?dry_run=true&limit=200" \
  -H "X-API-Key: $API_KEY_ADMIN"

curl -s -X POST "$CORE_API_URL/api/v1/contract-jobs/finalize-exhausted-new?limit=200" \
  -H "X-API-Key: $API_KEY_ADMIN"
```

Если MacBook оффлайн:
- Контрактные задачи остаются в `new`.
- Healthcheck пришлёт alert при отсутствии heartbeat.

## Troubleshooting
- Ошибки Telegram: проверить токен и права бота.
- Core API 500: проверить логи и `/health/detailed`.
- Бот буферизует лиды: проверить файл SQLite и доступность Core API.
- Нет worker heartbeat: проверить процесс на MacBook и сеть.
- Проверить живость worker'ов API-методом: `GET /api/v1/workers/status`.
