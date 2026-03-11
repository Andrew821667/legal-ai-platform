# Product Offer Sync Checklist

Обновлено: 2026-03-11

Цель:
- зафиксировать единую продуктовую и ценовую модель;
- не допускать расхождений между `lead-bot`, `web`, `contract-ai`;
- иметь reference-документ перед любыми copy/UI/payment-изменениями.

## 1. Текущее состояние

### Lead-bot
Источник:
- [apps/lead-bot/legacy/content.py](/Users/andrew/Мои%20AI%20проекты/legal-ai-platform/apps/lead-bot/legacy/content.py)

Текущая модель:
- бесплатная консультация `30 минут`;
- проектные пилоты и внедрения;
- ценовые ориентиры:
  - от `100 000 ₽` для стартовых сценариев;
  - `150 000 ₽+` для пилотов;
  - `300 000 ₽+` для рабочих контуров;
  - `500 000 ₽+` для интеграций/масштабирования.

### Web
Источники:
- [apps/web/components/LeadMagnets.tsx](/Users/andrew/Мои%20AI%20проекты/legal-ai-platform/apps/web/components/LeadMagnets.tsx)
- [apps/web/lib/faqData.ts](/Users/andrew/Мои%20AI%20проекты/legal-ai-platform/apps/web/lib/faqData.ts)

Текущая модель:
- бесплатная консультация `30 минут`;
- бесплатные lead magnets: гайд, демо-анализ, sample report;
- в FAQ и части copy говорится, что типовые решения начинаются от `300 000 ₽`.

### Contract AI
Источники:
- [apps/contract-ai/frontend/src/app/pricing/page.tsx](/Users/andrew/Мои%20AI%20проекты/legal-ai-platform/apps/contract-ai/frontend/src/app/pricing/page.tsx)
- [apps/contract-ai/src/api/payments/routes.py](/Users/andrew/Мои%20AI%20проекты/legal-ai-platform/apps/contract-ai/src/api/payments/routes.py)
- [apps/contract-ai/src/services/payment_service.py](/Users/andrew/Мои%20AI%20проекты/legal-ai-platform/apps/contract-ai/src/services/payment_service.py)

Текущая модель:
- public-facing UI переведен в `demo -> pilot -> working contour`;
- self-serve billing router выключен по умолчанию через feature flag;
- внутренние tier/payment артефакты еще остаются как legacy-техдолг.

## 2. Главная проблема

Главная исходная проблема была такой:

1. `Lead-bot` и `web`
- продают пилоты, внедрение и экспертную консультацию;
- позиционируют продукт как B2B/legal ops/contract automation проект.

2. `Contract AI`
- выглядел как self-serve SaaS с ежемесячной подпиской на индивидуального пользователя.

Сейчас public-facing часть уже выровнена, но внутренние артефакты старой модели еще требуют cleanup. Исходный конфликт создавал путаницу:
- для пользователя;
- для текстов;
- для будущих платежей;
- для аналитики;
- для приоритетов roadmap.

## 3. Target-модель

### Якорные продукты
- `Anchor 1`: `Contract_AI_System` как флагманский вход в автоматизацию договорного процесса.
- `Anchor 2`: `Пилот внедрения Legal AI / legal ops` как проектный сервис вокруг внедрения сценариев.

### Бесплатный вход
- `Бесплатная консультация 30 минут`
- `Гайд`
- `Демо-анализ`
- `Образец AI-отчета`

### Платный основной контур
- не подписка “для всех” по умолчанию;
- а `пилот`, `рабочий контур`, `интеграции`, `специальные платные консультации`.

### Special paid consultations
- отдельный слой;
- не заменяют бесплатную консультацию;
- не смешиваются с обычным lead flow.

## 4. Что считаем целевым позиционированием

### Bot
- ведет в:
  - бесплатную консультацию;
  - пилот;
  - внедрение;
  - специальные платные форматы только как отдельную опцию.
- не обещает self-serve SaaS тарифы.

### Web
- подтверждает ту же модель:
  - бесплатный вход;
  - пилот;
  - внедрение;
  - `Contract_AI_System` как флагман.
- не конфликтует с `lead-bot` по цене и формату.

### Contract AI
- либо:
  - временно репозиционируется как `demo/pilot interface` внутри общей платформы;
- либо:
  - позже выделяется в отдельный реальный SaaS-продукт с собственной go-to-market моделью.

На текущем этапе проекта правильнее первое.

## 5. Что считаем рассинхроном и должны убрать

- `[x]` Публичные SaaS pricing pages `1990/4990/19990 ₽/мес` убраны из public-facing `contract-ai` UI.
- `[x]` Старые Stripe subscription flows в `contract-ai` скрыты из runtime по умолчанию через feature flag.
- `[ ]` Любые тексты, где `contract-ai` продается как отдельная подписка, а остальные каналы как проектное внедрение.
- `[ ]` Разные обещания по бесплатной консультации и “следующему шагу”.
- `[ ]` Разные названия флагманского продукта между `bot`, `web`, `contract-ai`.

## 6. Решение на ближайший этап

### Оставляем
- бесплатная консультация `30 минут`;
- пилотный формат;
- проектные бюджеты и внедрение;
- `Contract_AI_System` как флагман.

### Не продвигаем активно
- self-serve monthly subscriptions в `contract-ai`.

### Что сделать следующим кодом
- `[x]` `contract-ai` pricing/page/payment copy приведены к pilot-first модели на публичном контуре.
- `[ ]` Синхронизировать названия офферов в `lead-bot` и `web`.
- `[ ]` Зафиксировать единый прайс-язык:
  - `бесплатная консультация`
  - `пилот`
  - `рабочий контур`
  - `интеграции`
  - `special paid consultation`
- `[ ]` Привязать будущую платежную систему к special paid consultation и/или pilot orders, а не к старой SaaS-подписке по умолчанию.

## 7. Источник истины на сейчас

До следующего продуктового пересмотра считать целевой моделью:
- `free consult + free magnets`
- `Contract_AI_System` как флагманский entry point
- `pilot / implementation / integrations` как основной платный контур
- `special paid consultation` как отдельный дополнительный слой

## 8. Контрольный вопрос перед каждой правкой copy/UI/payments

Перед изменением текста, оффера или платежного сценария задать себе вопрос:

`Эта правка усиливает pilot-first модель платформы или снова тянет проект в несогласованный self-serve SaaS?`
