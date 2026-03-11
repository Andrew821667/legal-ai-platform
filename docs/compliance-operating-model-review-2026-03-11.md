# Compliance Review By Operating Model

Обновлено: 2026-03-11

Цель документа:
- зафиксировать compliance-состояние проекта не по абстрактному коду, а по фактической операционной схеме;
- отделить уже подтвержденные меры от ручных действий владельца;
- не терять найденные разрывы между `lead-bot`, `web`, локальным runtime и публичными документами.

## 1. Scope и допущения

Этот review относится к `legal-ai-platform` в текущей схеме:
- `web`, `core-api`, `lead-bot`, `news` работают локально через `docker compose`;
- персональные данные и service secrets живут на локальной машине владельца проекта;
- `Contract_AI_System` считается внешним модулем и review его внутренних auth/billing/admin контуров сюда не входит;
- Telegram-боты и сайт могут использоваться с реальными пользователями, даже если runtime пока локальный.

Важно:
- ниже есть пункты, подтвержденные кодом;
- есть пункты, которые требуют ручного подтверждения владельца проекта и не могут быть доказаны одним репозиторием.

## 2. Подтвержденная операционная модель

### 2.1. Что собирает `web`

Источники:
- [apps/web/components/LeadCaptureForm.tsx](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/web/components/LeadCaptureForm.tsx)
- [apps/web/app/api/leads/route.ts](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/web/app/api/leads/route.ts)

Подтверждено кодом:
- сайт собирает `name`, `contact`, `segment`, `message`, `offer`, UTM-параметры и тех. признаки anti-abuse;
- обработка идет через `/api/leads`, затем данные уходят в `core-api`;
- форма требует чекбокс-согласие перед отправкой;
- при включении env на сайт могут ставиться `Google Analytics` и `Yandex Metrika`.

### 2.2. Что собирает `lead-bot`

Источники:
- [apps/lead-bot/legacy/content.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/content.py)
- [apps/lead-bot/legacy/handlers/user.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/handlers/user.py)
- [apps/lead-bot/legacy/ai_brain.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/ai_brain.py)
- [apps/lead-bot/legacy/database.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/database.py)

Подтверждено кодом:
- до персональной заявки бот запрашивает согласие на обработку ПД;
- для ИИ-режима отдельно запрашивается согласие на трансграничную передачу;
- бот сохраняет историю диалога и lead-данные;
- для истории диалога включена retention policy `90 дней`;
- есть команды на экспорт и отзыв/удаление данных;
- при ИИ-режиме в LLM уходит история диалога пользователя, а не только обезличенные структурированные поля.

### 2.3. Где сейчас живут данные

Источники:
- [infra/compose/docker-compose.prod.yml](/Users/andrew/Мои AI проекты/legal-ai-platform/infra/compose/docker-compose.prod.yml)
- [docs/architecture.md](/Users/andrew/Мои AI проекты/legal-ai-platform/docs/architecture.md)

Подтверждено кодом:
- основное хранилище платформы — локальный `Postgres`;
- `lead-bot` использует локальный `SQLite` fallback/runtime store;
- часть чувствительных runtime-артефактов живет в volumes и локальных файлах;
- `core-api` наружу по умолчанию связан с `127.0.0.1`, а не с `0.0.0.0`.

Инференс:
- если локальная машина и ее storage физически находятся в РФ, это помогает модели локализации ПД;
- если включены внешние cloud backups, sync folders или зарубежные сервисы хранения laptop backup, это уже отдельный фактический transfer path и его нужно описывать отдельно.

## 3. Что уже выглядит хорошо

### 3.1. Consent-разделение стало ближе к реальной модели

Сейчас проект уже лучше, чем раньше:
- базовое согласие на ПД отделено от согласия на ИИ/трансграничную передачу;
- у пользователя есть команды на экспорт, просмотр статуса и удаление данных;
- в `web` и `bot` есть явный legal disclaimer, что материалы носят информационный характер.

### 3.2. Есть технические меры, которые помогают compliance

Подтверждено кодом:
- anti-abuse и admin hardening внедрены;
- conversation retention работает автоматически;
- `core-api` меньше открыт наружу;
- secrets inventory и rotation checklist зафиксированы документально.

## 4. Реальные gaps по состоянию на 2026-03-11

### G1. Runtime-раскрытие оператора в боте неполное

Источники:
- [apps/lead-bot/legacy/content.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/content.py)
- [apps/lead-bot/legacy/config.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/config.py)

Факт:
- `lead-bot` умеет показывать `OPERATOR_NAME`, `OPERATOR_INN`, `OPERATOR_DETAILS`;
- в текущем локальном runtime эти переменные не заданы в root `.env`;
- значит в живом боте пользователь получает только generic-идентификацию оператора без реквизитов.

Вывод:
- это не баг кода, а операционный gap конфигурации;
- bot disclosure сейчас слабее, чем disclosure на сайте.

### G2. Public policy contour был неполным и требует живой проверки после исправления

Источники:
- [apps/lead-bot/legacy/config.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/config.py)
- [apps/lead-bot/legacy/content.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/content.py)
- [apps/web/app/privacy/page.tsx](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/web/app/privacy/page.tsx)
- [apps/web/app/terms/page.tsx](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/web/app/terms/page.tsx)

Статус на 2026-03-11:
- в `web` уже добавлены маршруты:
  - `/transborder-consent`
  - `/marketing-consent`
  - `/user-agreement`
  - `/ai-policy`
- disclosure-контур в коде стал согласованнее, чем был раньше.

Что осталось:
- проверить живые публичные URL после деплоя;
- убедиться, что bot env действительно указывает на эти маршруты, а не на старые внешние заглушки.

### G3. Public privacy/disclosure все еще требует окончательной синхронизации с фактическими processors

Источники:
- [apps/web/app/privacy/page.tsx](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/web/app/privacy/page.tsx)
- [apps/lead-bot/legacy/ai_brain.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/ai_brain.py)
- [apps/lead-bot/legacy/content.py](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/lead-bot/legacy/content.py)

Статус на 2026-03-11:
- privacy page уже дополнена упоминанием OpenAI-compatible providers;
- добавлена отдельная страница `/transborder-consent`.

Что осталось:
- зафиксировать точный фактический список провайдеров, которые реально используются в боевом режиме;
- проверить, что public wording совпадает с включенными env и операционной моделью.

### G4. Политика сайта и фактическое включение аналитики все еще требуют ручной верификации

Источники:
- [apps/web/app/layout.tsx](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/web/app/layout.tsx)
- [apps/web/app/privacy/page.tsx](/Users/andrew/Мои AI проекты/legal-ai-platform/apps/web/app/privacy/page.tsx)

Статус на 2026-03-11:
- privacy page уже уточняет, что счетчики включаются по конфигурации.

Что осталось:
- руками подтвердить, какие счетчики реально включены;
- не держать в публичной политике лишние сервисы, если они не используются.

### G5. Нет подтвержденного evidence по уведомлению РКН и по трансграничному уведомлению

Это не проверяется кодом. Но review должен зафиксировать:
- в репозитории нет доказательства подачи уведомления оператора в РКН;
- в репозитории нет доказательства подачи уведомления/позиции по трансграничной передаче;
- это ручной контур владельца проекта, а не техдолг кода.

### G6. Incident/regulatory response контур документирован слабо

Источники:
- [docs/secret-rotation-checklist.md](/Users/andrew/Мои AI проекты/legal-ai-platform/docs/secret-rotation-checklist.md)

Факт:
- есть rotation checklist и security hardening;
- но нет отдельного runbook:
  - кто фиксирует инцидент,
  - как сохраняются evidence,
  - кто и когда подает обязательные уведомления,
  - как документируется решение о необходимости уведомления.

Вывод:
- security-контур стал лучше;
- compliance incident response как операционный процесс пока не оформлен.

## 5. Что требует ручного подтверждения владельца

Ниже не “дырки в коде”, а вопросы, которые нужно закрыть вручную:

1. Подано ли уведомление оператора ПД в РКН и актуальны ли сведения в реестре.
2. Подана ли позиция/уведомление по трансграничной передаче там, где это нужно вашей фактической схеме.
3. Какие именно внешние сервисы реально включены в продовом/боевом режиме:
   - OpenAI-compatible LLM;
   - Google Analytics;
   - Yandex Metrika;
   - SMTP;
   - внешние backup/sync сервисы ноутбука.
4. Где физически и организационно хранятся резервные копии данных.
5. Какой фактический срок хранения для:
   - лидов;
   - переписки;
   - аналитических логов;
   - email/маркетинговых событий.

## 6. Практический список улучшений

### P1. Сделать до любого внешнего деплоя

1. Заполнить в runtime:
   - `OPERATOR_NAME`
   - `OPERATOR_INN`
   - `OPERATOR_DETAILS`
   - `PRIVACY_CONTACT_EMAIL`
2. Привести policy URLs к реальности:
   - либо создать страницы `/transborder-consent`, `/marketing-consent`, `/user-agreement`, `/ai-policy`;
   - либо перенастроить bot URLs на реально существующие документы.
3. Синхронизировать privacy/disclosure тексты между `web` и `lead-bot`.
4. Вручную проверить публичную доступность policy URLs.

### P2. Сделать до реальной эксплуатации с внешними пользователями

1. Подтвердить и задокументировать статус уведомления РКН.
2. Подтвердить и задокументировать модель трансграничной передачи.
3. Переписать privacy page так, чтобы она отражала фактических processors/получателей, а не только “типовой” список.
4. Описать channel-specific retention:
   - переписка бота — `90 дней`;
   - лидовые данные — по отдельному сроку;
   - условия анонимизации/удаления.

### P3. Сделать как операционный runbook

1. Отдельный incident/compliance playbook:
   - событие;
   - ответственный;
   - журнал;
   - evidence;
   - внешние уведомления;
   - пост-инцидентная ротация.
2. Зафиксировать, какие laptop/cloud backup paths считаются частью обработки ПД.

## 7. Статус по итогам review

- Кодовый слой согласий и прав пользователя: `существенно улучшен`.
- Runtime-disclosure оператора: `не закрыт до конца`.
- Public policy contour: `частично готов, но не синхронизирован`.
- Manual regulatory/compliance evidence: `не подтверждено этим репозиторием`.

## 8. Источники

Официальные и первичные источники, использованные для review:
- Роскомнадзор: [Форма уведомления об обработке персональных данных](https://pd.rkn.gov.ru/operators-registry/notification/form/)
- Роскомнадзор: [Разъяснения по уведомлению об обработке ПД и реестру операторов](https://22.rkn.gov.ru/p45908/)
- Роскомнадзор: [Разъяснения по трансграничной передаче персональных данных](https://22.rkn.gov.ru/p31985/)
- Роскомнадзор: [Разъяснения по изменениям в сведениях оператора и срокам уведомления](https://54.rkn.gov.ru/p14694/)
- Роскомнадзор: [Памятка по локализации баз персональных данных на территории РФ](https://82.rkn.gov.ru/p27359/)
- Роскомнадзор: [Разъяснение по согласию на обработку персональных данных](https://27.rkn.gov.ru/directions/pdn/p28531/)
- Роскомнадзор: [Разъяснения об обязанности оператора уведомлять об инцидентах по ПД](https://69.rkn.gov.ru/p40377/)

Важно:
- этот документ не заменяет индивидуальное юридическое заключение;
- он нужен как технически и операционно обоснованный review backlog для владельца проекта.
