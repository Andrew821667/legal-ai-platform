# Legal AI PRO - Профессиональный сайт для юридических AI-решений

Современный landing page для продвижения услуг по разработке AI-систем для автоматизации юридической работы.

## 🎯 О проекте

**Legal AI PRO** — это комплекс услуг по внедрению искусственного интеллекта в юридическую практику от команды практикующих юристов-разработчиков с многолетним опытом и глубокой экспертизой в AI.

### Основные направления:
- 📋 Автоматизация договорной работы (анализ, генерация, risk detection)
- ⚖️ Судебная и претензионная работа (анализ практики, генерация документов)
- 🏢 Корпоративное право и M&A (Due Diligence, корп. документооборот)
- 🌾 Земельное право и недвижимость
- 🛡️ Комплаенс и риск-менеджмент
- 💰 Налоговый комплаенс с AI-аналитикой (мониторинг изменений, прогноз рисков)
- 📊 Аналитика и отчетность
- 🔧 Кастомные AI-решения
- 💼 Юридический аутсорсинг + AI

## 🚀 Технологический стек

### Frontend
- **Next.js 16** - React framework с App Router
- **React 19** - Последняя версия React
- **TypeScript** - Строгая типизация
- **TailwindCSS 4** - Utility-first CSS framework
- **PostCSS** - CSS обработка

### Особенности
- ✅ Server-side rendering (SSR)
- ✅ Static generation для максимальной производительности
- ✅ Адаптивный дизайн (mobile-first)
- ✅ Плавные анимации и transitions
- ✅ SEO-оптимизация
- ✅ Lighthouse score 90+

## 📦 Установка и запуск

### Требования
- Node.js 18.0 или выше
- npm или yarn

### Установка зависимостей

```bash
npm install
```

### Запуск в режиме разработки

```bash
npm run dev
```

Сайт будет доступен по адресу: [http://localhost:3000](http://localhost:3000)

### Запуск с новым ядром (`core-api`)

1. Поднимите backend (`core-api`) на `http://127.0.0.1:8000`.
2. Создайте `apps/web/.env.local` на основе `.env.example` и заполните:
   - `CORE_API_URL`
   - `CORE_API_BOT_KEY` (или `API_KEY_BOT`) для формы лидов
   - `CORE_API_ADMIN_KEY` (или `API_KEY_ADMIN`)
3. Запустите сайт:

```bash
npm install
npm run dev
```

Проверка интеграции:
- [http://localhost:3000/api/admin/automation-controls](http://localhost:3000/api/admin/automation-controls) должен возвращать JSON с control plane.
- `POST /api/leads` на сайте проксирует лиды в `POST /api/v1/leads` core-api (source=`website_form`).

### Production build

```bash
npm run build
npm run start
```

### Линтинг

```bash
npm run lint
```

## 📁 Структура проекта

```
website/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Корневой layout (HTML structure)
│   ├── page.tsx           # Главная страница
│   └── globals.css        # Глобальные стили и анимации
├── components/            # React компоненты
│   └── Hero.tsx          # Hero секция (первый экран)
├── lib/                   # Утилиты и хелперы
├── public/               # Статические файлы (изображения, favicon)
├── next.config.js        # Конфигурация Next.js
├── tailwind.config.ts    # Конфигурация TailwindCSS
├── postcss.config.js     # PostCSS конфигурация
├── tsconfig.json         # TypeScript конфигурация
└── package.json          # Зависимости и скрипты
```

## 🎨 Дизайн система

### Цветовая палитра
- **Основной фон:** Slate градиент (900 → 800 → 700)
- **Акцент:** Amber (400, 600, 700)
- **Текст:** Slate (300 для вторичного, white для основного)
- **Прозрачность:** white/10, white/20 для glass-эффектов

### Типографика
- **Шрифт:** System fonts (Apple, SF, Roboto, Segoe UI)
- **Размеры:**
  - Заголовок: 5xl-7xl (72px на desktop)
  - Подзаголовок: xl-2xl
  - Основной текст: base-lg

### Анимации
- **Fade-in:** Плавное появление с translateY
- **Delays:** Последовательное появление элементов (0.2s, 0.4s, 0.6s)
- **Hover effects:** scale(1.05), цветовые transitions
- **Bounce:** Индикатор прокрутки

## 🛣️ Roadmap

### ✅ Фаза 1 (Завершено)
- [x] Настройка проекта (Next.js + TailwindCSS)
- [x] Hero секция с градиентом и статистикой
- [x] Адаптивный дизайн
- [x] Анимации появления

### 🎯 Фаза 2 (В разработке)
- [ ] Секция "Цифры и УТП" (4 карточки преимуществ)
- [ ] Интерактивный калькулятор ROI
- [ ] Секция "Услуги" (8 карточек)
- [ ] Секция "Кейсы" (3 детальных кейса)

### 📅 Фаза 3 (Планируется)
- [ ] Lead Magnet секция (3 опции)
- [ ] О команде (биография, достижения)
- [ ] Секция "Технологии"
- [ ] Контакты и Footer

### 🚀 Фаза 4 (Запуск)
- [ ] Финальная оптимизация производительности
- [ ] SEO оптимизация (meta tags, structured data)
- [ ] Интеграция с Telegram ботом
- [ ] Деплой на Vercel
- [ ] Подключение домена (опционально)

## 📊 Результаты и метрики

### Текущие показатели
- **Lighthouse Performance:** 95+
- **Bundle size:** < 200KB (gzipped)
- **First Contentful Paint:** < 1.5s
- **Time to Interactive:** < 2.5s

### Бизнес-цели
- **Конверсия посетитель → лид:** 5-10%
- **Время на сайте:** > 3 минуты
- **Bounce rate:** < 50%

## 🔗 Интеграции

### Telegram бот
Основной канал коммуникации с клиентами:
- Репозиторий: [legal-ai-bot](https://github.com/Andrew821667/legal-ai-bot)
- Функционал: AI-консультант, квалификация лидов, сбор контактов

### Планируемые интеграции
- Google Analytics / Yandex Metrika
- Calendly (запись на консультации)
- Email маркетинг (опционально)

## 🚀 Деплой

### Vercel (рекомендуется)
1. Подключить GitHub репозиторий к Vercel
2. Автоматический деплой при push в main
3. Получить URL: `legal-ai-website.vercel.app`

### Альтернативы
- Netlify
- Cloudflare Pages
- VDS с Node.js

## 👥 Команда

**Legal AI PRO Team** — юристы, которые сами пишут код и разрабатывают AI-системы.

### Наша экспертиза:
- 🎓 20+ лет юридической практики (договоры, M&A, банкротства, земельное право, ВЭД)
- 💻 Практический опыт программирования (Python, TypeScript, AI/ML)
- 🤖 Разработка и внедрение AI-систем для автоматизации юридической работы
- 🏢 Опыт работы CLO в крупных компаниях (агрохолдинги, банки, холдинги)

### Контакты
- 📧 Email: a.popov.gv@gmail.com
- 📱 Telegram: [@your_username](https://t.me/your_username)
- 💻 GitHub: [@Andrew821667](https://github.com/Andrew821667)

## 📄 Лицензия

См. [LICENSE](LICENSE)
