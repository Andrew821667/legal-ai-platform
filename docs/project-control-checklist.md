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
- `[~]` Убрать остаточные слабые dev/default значения и legacy-упоминания из docs/examples; критичные dev defaults и основные stale contract-ai quickstart/demo файлы уже очищены.
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
- `[x]` Стартовые и меню-тексты бота переписаны понятнее для нового пользователя, англицизмы в пользовательском copy сокращены.
- `[x]` Введена retention policy для `conversations`.
- `[x]` Legacy runtime-модули переведены на cached config singleton вместо множественных `Config()` на импорт.
- `[x]` Wildcard imports убраны из handler-модулей `lead-bot`.
- `[~]` Стартовый flow все еще перегружен legacy-логикой и может быть сокращен еще сильнее.
- `[~]` Разбить giant files (`database.py`, `callbacks.py`, `user.py`) на более узкие модули; уже вынесены `handlers/markup.py`, `handlers/start_payloads.py`, `handlers/admin_callbacks.py`, `database_conversations.py`, `database_consent.py`, `database_user_state.py`, `database_leads.py`, `database_reporting.py`, `database_knowledge.py`, `database_security.py`, но основной разрез еще не завершен.
- `[~]` Почистить import graph legacy; прямую связку `callbacks -> user` уже убрали, admin/runtime блок вынесен из `callbacks.py`, `database.py` уже сокращен до ~1610 строк, но модульная декомпозиция еще не закончена.
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

## 4. Web / Contract AI Integration Boundary
- `[x]` Зафиксировано, что реальный `Contract_AI_System` — отдельный репозиторий и внешний модуль относительно `legal-ai-platform`.
- `[x]` Граница ответственности между платформой и внешним контрактным модулем задокументирована.
- `[x]` `web`: reader conversion funnel закрыт admin session.
- `[x]` `web` и `lead-bot` говорят о `Contract_AI_System` как о внешнем модуле/флагманском направлении без обещаний, которые живут только в отдельном репозитории.
- `[x]` Инвентаризированы основные точки перехода из `web` и `lead-bot` в `Contract_AI_System`, заведён отдельный список entrypoints.
- `[x]` Зафиксирован канонический URL/entrypoint внешнего `Contract_AI_System` для `web`, `lead-bot` и docs.
- `[ ]` Проверить живой внешний entrypoint `Contract_AI_System` на реальном устройстве и убедиться, что CTA не ведут в тупик.
- `[!]` Полноценный аудит frontend/admin/auth/billing/test-matrix самого `Contract_AI_System` вести отдельно в репозитории `Contract-AI-System-`.
- `[x]` Явный legal disclaimer системно добавлен в web через CTA/lead/footer.

## 5. CI/CD и репозиторий
- `[x]` GitHub Actions починены: `CI/CD` и `Security` проходят в текущей private-repo схеме.
- `[x]` Dependabot PR приведены в стабильное состояние.
- `[x]` Docker images получают immutable tag по `github.sha`, а не только `latest`.
- `[x]` В `.gitignore` добавлен `venv/`.
- `[~]` Нужен отдельный проход по README/docs, чтобы убрать все устаревшие dev/security инструкции; критичные quickstart/demo хвосты уже почищены.
- `[ ]` При необходимости расширить CI на интеграционные проверки внешнего контрактного контура, не подменяя этим отдельный CI репозитория `Contract-AI-System-`.

## 6. Product / UX / позиционирование
- `[x]` Бесплатная консультация и специальные платные форматы концептуально разведены.
- `[x]` Ценовая и продуктовая модель между `lead-bot`, `web` и внешним `Contract_AI_System` синхронизирована на уровне integration boundary; полная унификация самого модуля должна вестись в отдельном репозитории.
- `[x]` Якорные продукты доведены до реальных текстов и маршрутов в `web` и `lead-bot`.
- `[ ]` Подготовить продуктовый контур для специальных платных консультаций:
  - products
  - orders
  - payments
  - webhook/provider flow
- `[ ]` Решить, где и как системно показывать special paid consultation без размывания бесплатного входа.

## 7. Compliance и операционная модель
- `[x]` Тексты consent/disclaimer стали ближе к реальной модели обработки данных.
- `[x]` Проведен отдельный compliance-review по реальной операционной модели: [compliance-operating-model-review-2026-03-11.md](/Users/andrew/Мои AI проекты/legal-ai-platform/docs/compliance-operating-model-review-2026-03-11.md)
- `[~]` Проверить и при необходимости обновить:
  - уведомление/позицию по 152-ФЗ
  - трансграничную передачу
  - реквизиты оператора
  - retention policy на уровне регламента, а не только кода
- `[~]` Проверить фактические публичные URL политик и их актуальность.
- `[~]` Привести `lead-bot` и `web` к одному public policy contour:
  - `privacy`
  - `transborder-consent`
  - `marketing-consent`
  - `user-agreement`
  - `ai-policy`
- `[x]` Missing legal routes добавлены в `web`: `transborder-consent`, `marketing-consent`, `user-agreement`, `ai-policy`.
- `[!]` Заполнить в runtime `OPERATOR_*` и `PRIVACY_CONTACT_EMAIL`, если публичный контур запускается с реальными пользователями.
- `[!]` Завести отдельный incident/compliance runbook для утечек/инцидентов с ПД.

## Осталось в первую очередь
- `[x]` Secret inventory + rotation checklist.
- `[x]` Web disclaimer в системных точках интерфейса.
- `[x]` Pricing/product sync между bot/web и внешним `Contract_AI_System`.
- `[~]` Legacy refactor: split files + remove wildcard imports + config singleton.
- `[x]` Отдельный compliance-review по реальной операционной схеме.
- `[~]` Закрыть operational gaps из compliance-review: operator disclosure, policy URLs, manual RKN contour.

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
