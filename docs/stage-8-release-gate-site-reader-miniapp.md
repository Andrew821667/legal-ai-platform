# Этап 8: Release Gate и приемка (site + reader + mini-app)

Дата: 2026-03-08

## 1. Go/No-Go чеклист

### 1.1 Сайт (`apps/web`)
- [ ] `npm run build` проходит без ошибок.
- [ ] Страницы `/`, `/for-lawyers`, `/for-business`, `/contract-ai-system`, `/solutions`, `/content-cases` открываются и не имеют тупиковых CTA.
- [ ] CTA-терминология едина: `Узнать -> Проверить -> Внедрить`.

### 1.2 Reader-бот
- [ ] Стартовое меню: `Узнать / Проверить / Решения / Поиск / Мое`.
- [ ] Deep-link из reader в mini-app сохраняет контекст пользователя.
- [ ] Reader-события пишутся в `core-api` без 4xx/5xx.

### 1.3 Mini-app
- [ ] Вкладки `Главная / Контент / Инструменты / Решения / Мое` открываются стабильно.
- [ ] Профиль и continue-state подгружаются при деградации upstream (stale fallback).
- [ ] CTA A/B для reader/mini-app управляется через `news.reader_cta_ab.enabled`.

### 1.4 Платформа в целом
- [ ] `core-api` healthy, required воркеры активны.
- [ ] Дубли polling-токенов между ботами отсутствуют.
- [ ] Сквозной flow `reader -> mini-app -> consultation/lead` проходит.

## 2. Обязательный smoke перед релизом

```bash
cd "/Users/andrew/Мои AI проекты/legal-ai-platform"
make smoke-bots
```

Состав smoke:
- подъем/проверка docker-стека;
- интеграционный тест control-plane и API;
- smoke reader digest;
- e2e `reader -> lead`;
- проверка логов на критичные ошибки (`Unauthorized`, `Connection refused`, `NameResolutionError`, polling conflict).

## 3. Приемка межканальных сценариев (ручная)

1. Сайт -> reader:
- проверить переходы CTA в Telegram и корректные UTM/source-action маркеры.

2. Reader -> mini-app:
- открыть mini-app из reader, убедиться в сохранении контекста и корректной навигации.

3. Mini-app -> решение/консультация:
- проверить переход в ветку консультации/решений и запись событий в funnel.

4. Admin контур:
- проверить разделы `Автоматизация`, `Воркеры`, `Reader-метрики`, `Reader CTA A/B`.
- убедиться, что переключатели меняют control-plane без перезапуска сервисов.

## 4. Rollback-план

1. Зафиксировать инцидент:
- время, сервис, симптом (5xx/timeout/UX-block).

2. Быстрый rollback по сервисам:
```bash
cd "/Users/andrew/Мои AI проекты/legal-ai-platform"
docker compose -f infra/compose/docker-compose.prod.yml up -d --no-deps core-api web news-reader-bot news-admin-bot news-reader-digest
```

3. Если проблема в релизных изменениях:
- откатить на предыдущий git tag/commit на сервере;
- повторить `docker compose ... up -d --build` для build-сервисов;
- проверить `health` и `make smoke-bots`.

4. Если проблема в control-plane настройках:
- вернуть стабильные значения через admin-бот (слоты/лимиты/CTA split);
- при необходимости временно отключить `news.reader_cta_ab.enabled`.

5. Критерий завершения rollback:
- `core-api` healthy;
- воркеры активны;
- ключевые user-flow работают;
- smoke проходит без критичных ошибок.

