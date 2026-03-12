# Contract AI Entrypoints

Обновлено: 2026-03-12

Цель:
- иметь инвентарь точек входа из `legal-ai-platform` во внешний `Contract_AI_System`;
- не допускать тупиковых CTA и рассинхрона между `web`, `lead-bot` и docs.

## Канонический entrypoint

- env для `web`: `NEXT_PUBLIC_CONTRACT_AI_SYSTEM_URL`
- env для `lead-bot`: `CONTRACT_AI_SYSTEM_URL`
- root env: `CONTRACT_AI_SYSTEM_URL`

Правило:
- если внешний URL задан, action-кнопки ведут в него;
- если не задан, action-кнопки fallback'ятся на внутреннюю инфостраницу `/contract-ai-system`.

## Инфостраница vs рабочий модуль

- `/contract-ai-system` — это инфостраница платформы, а не сам внешний модуль.
- Внешний `Contract_AI_System` — отдельный рабочий контур.

Это разделение должно сохраняться в copy и навигации.

## Проверенные точки входа

### Web
- header CTA `Открыть модуль / Попробовать продукт`
- главная страница: primary CTA в hero
- страница `/contract-ai-system`: отдельная кнопка открытия внешнего модуля
- footer: ресурс `Проверить договор`
- mini-app home: recommended step для `validate`
- mini-app tools: карточка `Проверка договора AI`
- mini-app flow card: кнопка `🧪 Проверить в Contract_AI_System`

### Lead-bot
- меню `🧪 Проверить договор`
- URL-кнопка `🖥 Открыть Contract_AI_System` в карточке договорного модуля, если внешний URL задан

## Что еще остается проверять вручную

1. Что внешний URL реально доступен с того устройства, где пользователь кликает.
2. Что у action-кнопок нет рассинхрона с copy на лендингах и в боте.
3. Что при недоступности внешнего модуля пользователь все равно может уйти в консультацию/пилот, а не в тупик.

## Опциональная CI-проверка

Для репозитория `legal-ai-platform` можно включить легкий smoke внешнего entrypoint в GitHub Actions.

Нужные repo variables:
- `CONTRACT_AI_SYSTEM_SMOKE_URL`
- `CONTRACT_AI_SYSTEM_EXPECTED_MARKER` — необязательно

Логика:
- если `CONTRACT_AI_SYSTEM_SMOKE_URL` не задан, job пропускается;
- если задан, CI проверяет, что внешний entrypoint отвечает `2xx`;
- если задан `CONTRACT_AI_SYSTEM_EXPECTED_MARKER`, CI дополнительно ищет этот маркер в ответе.
