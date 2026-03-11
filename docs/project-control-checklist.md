# Project Control Checklist

Обновлено: 2026-03-11

Статусы:
- `[x]` сделано и проверено
- `[~]` сделано частично, нужен еще один проход
- `[ ]` не сделано
- `[!]` требует не кода, а ручного/организационного действия

## Как использовать
- Перед новым циклом работ: сначала смотреть раздел `Осталось`.
- Перед `commit/push`: проходить раздел `Финальная сверка`.
- После каждого крупного блока: обновлять статусы, а не держать их в памяти.

## 1. Security и доступы
- `[x]` Убран runtime-path с `admin123` и legacy auth fallback из web admin.
- `[x]` `lead-bot`: prompt injection не только детектируется, но и defang/block до отправки в LLM.
- `[x]` `lead-bot`: extracted lead JSON проходит строгую нормализацию и валидацию.
- `[x]` `lead-bot`: введены human-only gate, quarantine, anti-abuse, incident log.
- `[x]` `web`: `/api/leads` усилен honeypot/time-trap/rate-limit/adaptive challenge.
- `[x]` `web-admin`: hash password + TOTP + persistent throttling + revokeable sessions.
- `[x]` `core-api`: внешний perimeter ужесточен, лишняя экспозиция сокращена.
- `[x]` Зависимости обновлены, открытые Dependabot alerts закрыты.
- `[~]` Убрать остаточные слабые dev/default значения и legacy-упоминания из всех docs/examples.
- `[x]` Заведен единый `secret inventory` по всем сервисам.
- `[x]` Заведен `secret rotation checklist` с журналом и правилами ротации.
- `[!]` Реально ротировать боевые токены/ключи по регламенту, не только держать код готовым.

## 2. Lead-bot
- `[x]` Ускорены callback-переходы, убраны лишние roundtrip в hot path.
- `[x]` Добавлен perf-профайлинг callback/update.
- `[x]` Профиль пользователя вынесен в верх меню и явно акцентирован.
- `[x]` Добавлен onboarding-текст на первом входе про выбор профиля.
- `[x]` Добавлен мягкий CTA на Telegram-канал в релевантных экранах.
- `[x]` Consent больше не стоит жесткой стеной до базовой ценности.
- `[x]` Добавлен legal disclaimer и обновлены consent-тексты.
- `[x]` Введена retention policy для `conversations`.
- `[x]` Legacy runtime-модули переведены на cached config singleton вместо множественных `Config()` на импорт.
- `[~]` Wildcard imports убраны из основных handler-модулей; дальнейшая чистка import graph legacy еще нужна.
- `[~]` Стартовый flow все еще перегружен legacy-логикой и может быть сокращен еще сильнее.
- `[ ]` Разбить giant files (`database.py`, `callbacks.py`, `user.py`) на более узкие модули.
- `[~]` Убрать wildcard imports и почистить import graph.
- `[x]` Перевести legacy config/init на единый singleton/cache pattern.

## 3. News / Reader
- `[x]` Исправлена ошибка `workers_activity() takes 2 positional arguments but 4 were given`.
- `[x]` Worker UX и operational control приведены в рабочее состояние.
- `[x]` Reader: очищены тексты от мусорных спецсимволов и сломанной разметки.
- `[x]` Reader: восстановлены кнопки открытия оригинала статьи/поста, где данные доступны.
- `[x]` Reader: добавлен perf-профайлинг экранов и запросов в `core-api`.
- `[x]` Исправлены тавтологичные футеры в reader-текстах.
- `[x]` Обычные news `draft/review` теперь чистятся по retention.
- `[x]` `weekly_review` живет отдельно и не режется как обычная новость.
- `[~]` Проверить, что для всех старых публикаций есть backfill данных на `source_url/channel_post_url`, если нужны кнопки открытия оригинала.

## 4. Web / Contract AI
- `[x]` `contract-ai`: закрыт frontend auth bypass.
- `[x]` `contract-ai`: закрыта неавторизованная раздача договоров как static files.
- `[x]` `contract-ai`: убраны insecure dev/demo helper flows.
- `[x]` `contract-ai`: frontend снова проходит `type-check` и `build`.
- `[x]` `contract-ai`: включен в основной CI минимумом smoke/build/type-check.
- `[x]` `web`: reader conversion funnel закрыт admin session.
- `[x]` `contract-ai`: self-serve pricing/subscription public contour выключен по умолчанию, public UI переведен в pilot-first модель.
- `[~]` `contract-ai` пока в CI не покрыт полноценным test-matrix, только разумным базовым контуром.
- `[x]` Явный legal disclaimer системно добавлен в web через CTA/lead/footer.

## 5. CI/CD и репозиторий
- `[x]` GitHub Actions починены: `CI/CD` и `Security` проходят в текущей private-repo схеме.
- `[x]` Dependabot PR приведены в стабильное состояние.
- `[x]` Docker images получают immutable tag по `github.sha`, а не только `latest`.
- `[x]` В `.gitignore` добавлен `venv/`.
- `[~]` Нужен отдельный проход по README/docs, чтобы убрать все устаревшие dev/security инструкции.
- `[ ]` При необходимости расширить CI на более глубокие тесты `contract-ai` и интеграционные сценарии.

## 6. Product / UX / позиционирование
- `[x]` Бесплатная консультация и специальные платные форматы концептуально разведены.
- `[~]` Ценовая и продуктовая модель между `lead-bot`, `web`, `contract-ai` проаудирована; `contract-ai` public runtime уже переведен в pilot-first модель, но глубинная унификация текстов и внутренних tier-артефактов еще впереди.
- `[~]` Якорные продукты зафиксированы на уровне target-модели; нужно довести до реальных текстов и маршрутов.
- `[ ]` Подготовить продуктовый контур для специальных платных консультаций:
  - products
  - orders
  - payments
  - webhook/provider flow
- `[ ]` Решить, где и как системно показывать special paid consultation без размывания бесплатного входа.

## 7. Compliance и операционная модель
- `[x]` Тексты consent/disclaimer стали ближе к реальной модели обработки данных.
- `[ ]` Провести отдельный compliance-review не по коду, а по реальной операционной модели.
- `[ ]` Проверить и при необходимости обновить:
  - уведомление/позицию по 152-ФЗ
  - трансграничную передачу
  - реквизиты оператора
  - retention policy на уровне регламента, а не только кода
- `[ ]` Проверить фактические публичные URL политик и их актуальность.

## Осталось в первую очередь
- `[x]` Secret inventory + rotation checklist.
- `[x]` Web disclaimer в системных точках интерфейса.
- `[~]` Pricing/product sync между bot/web/contract-ai.
- `[ ]` Legacy refactor: split files + remove wildcard imports + config singleton.
- `[ ]` Отдельный compliance-review по реальной операционной схеме.

## Финальная сверка перед commit/push
- `[ ]` `git status` понятен, нет случайных чужих правок.
- `[ ]` Все новые env/docs изменения отражены в `.env.example` и/или соответствующем README.
- `[ ]` Есть тесты или хотя бы smoke на измененный критичный путь.
- `[ ]` Локально пройдены нужные `pytest` / `npm build` / `lint` / smoke.
- `[ ]` Нет явных debug-логов, `alert()`, test bypass, demo fallback.
- `[ ]` Нет новых security-regressions и временных ослаблений защиты.
- `[ ]` Изменения отражены в этом checklist, если они меняют фактический статус проекта.

## Финальная сверка перед деплоем
- `[ ]` Нужные секреты актуальны и не используют слабые defaults.
- `[ ]` Контейнеры стартуют на новой версии без runtime errors.
- `[ ]` Healthcheck и smoke проходят.
- `[ ]` Проверены боты на живых ключевых сценариях:
  - `lead-bot`
  - `reader`
  - `news admin`
- `[ ]` Проверены web/admin критичные маршруты.
- `[ ]` Понятно, какие ручные post-deploy проверки должен сделать владелец проекта.
