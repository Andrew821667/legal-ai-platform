# Этап 7: Нагрузочный и UX-hardening — отчет закрытия

Дата: 2026-03-07

## Закрытые задачи этапа

1. Профилирование `apps/web` и reader/admin-ботов:
- устранены лишние повторные вызовы `automation-controls`/`workers` в admin-боте;
- проверены и оптимизированы client->web->core вызовы mini-app state.

2. Снижение лишних запросов в reader и mini-app:
- убран дублирующий sync-вызов профиля при deep-link событиях mini-app;
- добавлен debounce профиля mini-app перед PATCH в core;
- добавлен dedup событий mini-app в коротком окне;
- оптимизирован home-screen reader-бота (параллельные операции без дубля fallback-запроса профиля).

3. Кэширование контента и профильных данных:
- добавлен read-cache + stale fallback для web reader proxy (`continue-state`, `miniapp/profile`, `conversion-funnel`);
- добавлен in-flight dedup в `core_reader_bridge` для исключения параллельных дублей GET.

4. Защита от деградации внешних API:
- добавлены timeout/fallback паттерны на mini-app API вызовах;
- для weekly-digest reader-бота введен timeout LLM-вызова с гарантированным fallback-дайджестом.

## Критерий выхода этапа

- Ключевые flow (`reader`, `mini-app`, `admin`) продолжают работу при временных сбоях upstream.
- Нет критичных UX-блокировок из-за подвисших внешних запросов.
- Снижен контрольный шум по повторным API вызовам в типичных сценариях навигации.
