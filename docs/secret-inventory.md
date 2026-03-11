# Secret Inventory

Обновлено: 2026-03-11

Цель документа:
- не держать секреты “в голове”;
- понимать, какой ключ к какому контуру относится;
- не путать `prod`, `local`, `bot`, `admin`, `news`, `reader`.

Правила:
- реальные значения не записывать в git;
- в этом файле хранить только перечень, назначение и правила ротации;
- после любой ротации обновлять дату и комментарий в разделе `История`.

## 1. Core / Infrastructure

| Secret | Где используется | Критичность | Где хранится сейчас | Комментарий |
|---|---|---:|---|---|
| `POSTGRES_PASSWORD` | `postgres`, `core-api`, `news`, `web-admin store`, смежные backend сервисы | высокая | локальный `.env` | Не использовать слабые defaults вне локальной машины |
| `DATABASE_URL` | backend-приложения | высокая | локальный `.env` | Производная от postgres credentials, ротируется вместе с ними |
| `API_KEY_BOT` | доступ ботов к `core-api` | высокая | локальный `.env` | Scope `bot` |
| `API_KEY_NEWS` | доступ news-контура к `core-api` | высокая | локальный `.env` | Scope `news` |
| `API_KEY_WORKER` | worker/admin automation flows | высокая | локальный `.env` | Scope `worker` |
| `API_KEY_ADMIN` / `CORE_API_ADMIN_KEY` | admin/server-side privileged routes | критическая | локальный `.env` | Не использовать в клиентском коде |

## 2. Telegram Bots

| Secret | Где используется | Критичность | Где хранится сейчас | Комментарий |
|---|---|---:|---|---|
| `LEAD_BOT_TOKEN` | `lead-bot` | критическая | локальный `.env` | Полный захват лид-бота при утечке |
| `TELEGRAM_BOT_TOKEN` | fallback и часть общих flows | критическая | локальный `.env` | Проверить, не дублирует ли `LEAD_BOT_TOKEN` |
| `NEWS_ADMIN_BOT_TOKEN` | news admin bot | критическая | локальный `.env` | |
| `READER_BOT_TOKEN` | reader bot, miniapp verify | критическая | локальный `.env` | |
| `ALERT_BOT_TOKEN` | security/ops alerts | высокая | локальный `.env` | |

## 3. Telegram MTProto / ingest

| Secret | Где используется | Критичность | Где хранится сейчас | Комментарий |
|---|---|---:|---|---|
| `TELEGRAM_API_ID` | Telegram ingest | высокая | локальный `.env` | Ротировать вместе с `API_HASH`, если есть подозрение на компрометацию |
| `TELEGRAM_API_HASH` | Telegram ingest | высокая | локальный `.env` | |
| `TELEGRAM_SESSION_NAME` / `TELEGRAM_SESSION_NAME_DOCKER` | session artifacts | критическая | локальный `.env` + volume | Сами session-файлы тоже считаются чувствительными |

## 4. LLM / внешние AI providers

| Secret | Где используется | Критичность | Где хранится сейчас | Комментарий |
|---|---|---:|---|---|
| `OPENAI_API_KEY` | `lead-bot`, `news`, смежные AI flows | высокая | локальный `.env` | Может использоваться и для OpenAI-compatible провайдеров |
| `DEEPSEEK_API_KEY` | news legacy | высокая | локальный `.env` | Если реально используется отдельным ключом |
| `PERPLEXITY_API_KEY` | news legacy | средняя/высокая | локальный `.env` | |

## 5. Web Admin / Auth

| Secret | Где используется | Критичность | Где хранится сейчас | Комментарий |
|---|---|---:|---|---|
| `ADMIN_PANEL_PASSWORD_HASH` | web admin login | критическая | локальный `.env` | Хэш, но все равно чувствительный auth-артефакт |
| `ADMIN_PANEL_TOTP_SECRET` | второй фактор admin panel | критическая | локальный `.env` | При утечке ослабляет 2FA |
| `ADMIN_PANEL_SESSION_SECRET` | подпись admin session | критическая | локальный `.env` | Ротация инвалидирует существующие сессии |

## 6. Analytics / integrations / mail

| Secret | Где используется | Критичность | Где хранится сейчас | Комментарий |
|---|---|---:|---|---|
| `GA4_CREDENTIALS` | web analytics integrations | средняя/высокая | локальный `.env` | JSON service account |
| `YM_ACCESS_TOKEN` | Yandex Metrika API | средняя | локальный `.env` | |
| `GITHUB_TOKEN` | web/admin GitHub integrations | средняя/высокая | локальный `.env` | Не путать с локальным `gh auth` |
| `SMTP_PASSWORD` | `lead-bot` email flows | высокая | локальный `.env` | App password, не обычный логин |

## 7. Runtime storage, которое тоже считать секретным

Не только env-переменные:
- `apps/news/legacy/telegram_bot*` и bind-mounted session files;
- `data/web-admin-security.json`;
- cookie/session signing secrets в runtime env;
- локальные бэкапы `.env`, экспортов и docker volumes.

## 8. Где должен жить source of truth

Сейчас:
- локальный root `.env`;
- отдельные `.env.example` как документация;
- runtime values в docker compose env propagation.

Целевое правило:
- source of truth для реальных секретов — только локальный/серверный secret store или защищенный `.env`, не git;
- `.env.example` содержит только имена и безопасные примеры;
- этот inventory хранит состав, а не значения.

## 9. История / контроль

| Дата | Что меняли | Кто менял | Комментарий |
|---|---|---|---|
| 2026-03-11 | Создан initial secret inventory | Codex + владелец проекта | Нужна следующая реальная ротация боевых токенов |
