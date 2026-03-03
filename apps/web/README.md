# Legal AI PRO Web

Публичный сайт и веб-админка проекта `legal-ai-platform`.

## Что здесь есть

- публичный лендинг для услуг Legal AI PRO;
- форма захвата лида с отправкой в `core-api`;
- отдельная страница `/admin` для внутренней панели;
- прокси-маршруты для админских и lead-операций.

## Стек

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS 4

## Локальный запуск

Требования:
- Node.js 18+
- запущенный `core-api`

Установка:

```bash
npm install
```

Создайте `apps/web/.env.local` на основе `.env.example`.

Минимально нужно задать:

```env
CORE_API_URL=http://127.0.0.1:8001
NEXT_PUBLIC_CORE_API_URL=http://127.0.0.1:8001
CORE_API_BOT_KEY=...
CORE_API_ADMIN_KEY=...
ADMIN_PANEL_PASSWORD=...
```

Запуск:

```bash
npm run dev
```

Сборка:

```bash
npm run build
```

## Интеграции

- `POST /api/leads` проксирует лиды в `core-api`
- `/api/admin/*` работает через server-side прокси и не должен светить admin credentials в клиент
- `/admin` использует пароль из `ADMIN_PANEL_PASSWORD`

## Важные правила

- не использовать `NEXT_PUBLIC_ADMIN_PASSWORD`;
- не публиковать на сайте недоказуемые кейсы, отзывы и numeric claims;
- все сильные обещания по срокам, экономии и метрикам должны жить только в индивидуальном предложении, а не в публичном лендинге.
