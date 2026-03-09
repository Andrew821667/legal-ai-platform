# Technical Audit Report

Дата: 2026-03-09  
Контур: `core-api`, `lead-bot`, `news` (admin/reader), `web`, docker-стек

## Критичные находки (по приоритету)

1. `P0` — удаление лида падало с `500` из-за FK-ссылок на `events`.
- Симптом: при `DELETE /api/v1/leads/{id}` возникал `IntegrityError`, если на лид ссылались `events`.
- Корень: удаление parent-сущности без предваренного detach зависимых строк.
- Статус: **исправлено**.
- Где:
  - [apps/core-api/core_api/routers/leads.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/core-api/core_api/routers/leads.py):216
  - [apps/core-api/tests/test_leads_api.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/core-api/tests/test_leads_api.py):253

2. `P1` — линтерный runtime-риск в news publish loop (`F821`).
- Симптом: статический анализ ловит undefined name в аннотации `CoreClient`.
- Где: [apps/news/news/publish_loop.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/news/news/publish_loop.py):17
- Статус: **не исправлено**, нужно закрыть отдельным патчем (через `TYPE_CHECKING`/явный импорт типа).

3. `P1` — высокий объем техдолга в lint-слое.
- Симптом: большое число ошибок Ruff (включая wildcard imports, redefinition, style/runtime mix).
- Статус: **не исправлено** (проект функционально рабочий, но кодовая база перегружена долгом).

4. `P2` — монолитные файлы затрудняют сопровождение.
- Где:
  - [apps/news/news/admin_bot.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/news/news/admin_bot.py) — 9223 строки
  - [apps/lead-bot/legacy/database.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/database.py) — 2578 строк
  - [apps/news/legacy/app/bot/handlers.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/news/legacy/app/bot/handlers.py) — 4495 строк
- Статус: **не исправлено** (архитектурный backlog).

5. `P2` — мусорные backup-файлы в runtime-папке legacy news-бота.
- Где:
  - [apps/news/legacy/app/bot/handlers.py.backup2](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/news/legacy/app/bot/handlers.py.backup2)
  - [apps/news/legacy/app/bot/handlers.py.bak_final](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/news/legacy/app/bot/handlers.py.bak_final)
- Статус: **не исправлено**.

## Исправлено в рамках аудита

1. Фикс `DELETE lead` с предваренным detach зависимостей:
- `events.lead_id -> NULL`
- `contract_jobs.lead_id -> NULL`
- добавлен audit detail по количеству detaches.

2. Добавлен regression-тест на сценарий удаления лида с привязанным `event`.
- Проверка: `204` + `event` остается, но `lead_id is None`.

3. Почищен `.env.example` от дубликатов ключей.
- Где: [/.env.example](/Users/andrew/Мои AI проекты/legal-ai-platform/.env.example):106
- Убраны дубли:
  - `NEWS_GENERATE_INTERVAL_SECONDS`
  - `NEWS_PUBLISH_INTERVAL_SECONDS`

## Что проверено (статус smoke/quality)

На момент аудита:
- `core-api` unit/API тесты: **green**
- `apps/news` тесты: **green**
- `apps/lead-bot/legacy` тесты: **green**
- `apps/web` build: **green**
- e2e smoke по ботам: **green** после фикса `DELETE lead`.

Примечание: lint-контур остается красным (техдолг), это не блокирует текущую функциональность, но повышает риск регрессий при масштабировании.

## Архитектурные замечания (senior review)

1. Legacy dual-run (часть логики в legacy, часть в core-api) увеличивает операционный риск.
2. Слишком крупные модульные границы в `admin_bot.py`/legacy handlers ухудшают скорость изменений.
3. Нужна отдельная программа «stabilize then split»: сначала фиксация контрактов модулей, затем декомпозиция по bounded-контекстам.
4. Для production-ready фазы нужен отдельный hardening-пакет:
- закрыть `F821` и runtime-lint-класс ошибок,
- удалить backup-файлы,
- ввести baseline CI-gates по критичным lint-кодам (`F`, `E9`, `B`),
- документировать worker-failure recovery и SLA-пороговые алерты.

## Рекомендуемый следующий шаг

1. Закрыть runtime-lint блок (`F821` и близкие `F*`) отдельным быстрым PR.
2. Провести controlled split для `admin_bot.py` на модули:
- navigation/render,
- queue/calendar,
- generation/create-flow,
- worker/system.
3. Удалить legacy backup-файлы и закрепить pre-commit правило против `.bak/.backup*`.
4. После этого повторить полный smoke + regression.
