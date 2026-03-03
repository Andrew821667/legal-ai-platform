# 🔐 Админ-панель - Документация

Полнофункциональная админ-панель для мониторинга и управления сайтом Legal AI PRO.

## 🚀 Быстрый старт

### Вход в админ-панель

**Комбинация клавиш:**
- **Windows/Linux:** `Ctrl` + `Shift` + `A`
- **macOS:** `Cmd` + `Shift` + `A`

При нажатии откроется модальное окно с формой авторизации.

**Пароль по умолчанию:** `admin123`

> ⚠️ **Важно!** Измените пароль в production окружении через переменную окружения

---

## ⚙️ Настройка

### Изменение пароля

1. Создайте файл `.env.local` в корне проекта (если еще не создан)
2. Добавьте переменную:

```env
ADMIN_PANEL_PASSWORD=ваш_безопасный_пароль
```

3. Перезапустите dev сервер

### Production настройка

Для Vercel/Netlify добавьте переменные окружения в настройках проекта:

```env
# Пароль админ-панели
ADMIN_PANEL_PASSWORD=ваш_безопасный_пароль

# GitHub Token (опционально, для приватных репозиториев)
GITHUB_TOKEN=ghp_ваш_токен_здесь
```

### Настройка реальной аналитики

Админ-панель поддерживает интеграцию с **Google Analytics 4** и **Yandex Metrika** для отображения реальных данных посещаемости.

#### Google Analytics 4 (рекомендуется для международной аудитории)

1. **Создайте Service Account в Google Cloud:**
   - Откройте https://console.cloud.google.com/
   - Создайте или выберите проект
   - Перейдите в **IAM & Admin → Service Accounts**
   - Нажмите **Create Service Account**
   - Заполните имя и описание
   - Нажмите **Create and Continue**

2. **Дайте доступ к Google Analytics:**
   - Скопируйте email Service Account (вида `xxx@xxx.iam.gserviceaccount.com`)
   - Откройте Google Analytics 4: https://analytics.google.com/
   - Перейдите в **Admin → Property → Property Access Management**
   - Нажмите **+** и **Add users**
   - Вставьте email Service Account
   - Выберите роль: **Viewer**
   - Нажмите **Add**

3. **Получите credentials и Property ID:**
   - В Service Account нажмите **Keys → Add Key → Create new key**
   - Выберите формат **JSON**
   - Сохраните файл
   - Откройте файл и скопируйте **весь JSON**
   - В Google Analytics скопируйте **Property ID** (Admin → Property Settings)

4. **Добавьте в Vercel Environment Variables:**
   ```env
   GA4_PROPERTY_ID=123456789
   GA4_CREDENTIALS={"type":"service_account","project_id":"...весь JSON..."}
   ```

#### Yandex Metrika (рекомендуется для российской аудитории)

1. **Получите Counter ID:**
   - Откройте https://metrika.yandex.ru/
   - Скопируйте номер счетчика (8-значное число)

2. **Получите OAuth токен:**
   - Откройте эту ссылку:
     ```
     https://oauth.yandex.ru/authorize?response_type=token&client_id=c2e6111dbaff4ae883c43a9bf8ac9231
     ```
   - Авторизуйтесь в Яндекс
   - Разрешите доступ
   - Скопируйте токен из URL (после `access_token=`)

3. **Добавьте в Vercel Environment Variables:**
   ```env
   YM_COUNTER_ID=12345678
   YM_ACCESS_TOKEN=y0_AgAAAAA...
   ```

#### Использование обеих систем

Вы можете настроить **обе системы одновременно**!

Админ-панель будет:
- Комбинировать данные из обеих источников
- Показывать среднее значение метрик
- Объединять топ страниц и источники трафика
- Отображать какие системы активны

#### Site URL (для production)

```env
NEXT_PUBLIC_SITE_URL=https://your-site.vercel.app
```

Эта переменная нужна для правильной работы API endpoints в production.

---

### GitHub Token (опционально)

Для получения данных из **приватных** репозиториев нужен GitHub Token:

1. Перейдите на https://github.com/settings/tokens
2. Создайте **Personal Access Token (Classic)**
3. Выберите scope: `repo` (для доступа к приватным репозиториям)
4. Скопируйте токен
5. Добавьте в `.env.local`:
   ```env
   GITHUB_TOKEN=ghp_ваш_токен
   ```

**Для публичных репозиториев токен не обязателен**, API работает без него (с ограничением 60 запросов/час).

---

## 📊 Функции админ-панели

### 1. SEO & Аналитика

Отслеживание основных метрик сайта с **реальными данными** из Google Analytics 4 и/или Yandex Metrika.

> 📊 **Источники данных:**
> - **Google Analytics 4** - для международной аудитории
> - **Yandex Metrika** - для российской аудитории
> - **Комбинированный режим** - используйте обе системы одновременно
>
> Без настройки аналитики показываются нулевые значения.

#### Периодическая статистика
- **Сегодня / Неделя / Месяц:**
  - Визиты
  - Просмотры страниц
  - Уникальные посетители
  - Bounce Rate
  - Среднее время на сайте
  - Конверсии

#### Топ страниц
- Список самых посещаемых страниц
- Количество визитов на каждую
- Среднее время просмотра

#### Источники трафика
- Органический поиск
- Прямые переходы
- Социальные сети
- Реферальные ссылки
- Процентное распределение

### 2. Технические данные

Мониторинг производительности и технического состояния:

#### Производительность
- **Lighthouse Score** - общая оценка производительности
- **FCP** (First Contentful Paint) - время до первой отрисовки
- **LCP** (Largest Contentful Paint) - время загрузки основного контента
- **TTI** (Time to Interactive) - время до интерактивности
- **CLS** (Cumulative Layout Shift) - стабильность макета
- **Bundle Size** - размер JavaScript бандла
- **Gzipped Size** - размер после сжатия

#### Серверные метрики
- **Uptime** - время работы без сбоев
- **Response Time** - среднее время отклика
- **Requests** - количество запросов
- **Error Rate** - процент ошибок

#### Информация о деплое
- Текущая версия
- Время последнего деплоя
- Окружение (Production/Staging)
- Регион сервера

### 3. GitHub & SEO Reports

Интеграция с GitHub для отслеживания SEO отчетов и задач:

#### SEO Отчет (из seo-ai-models)
- **SEO Score** - общая оценка (0-100) с цветовой индикацией
- **Predicted Position** - прогнозируемая позиция в поиске
- **Readability** - оценка читабельности контента
- **E-E-A-T Score** - оценка экспертности, авторитетности, надежности
- Дата последнего отчета
- Прямая ссылка на полный отчет в GitHub

#### Issues Статистика
- **Всего Issues** - общее количество
- **Открыто/Закрыто** - текущий статус
- **SEO Issues по приоритетам:**
  - Critical (критические)
  - High (высокие)
  - Medium (средние)

#### Приоритетные SEO задачи
- Топ-5 открытых задач с высоким приоритетом
- Метки приоритета (Critical/High/Medium)
- Номера и заголовки issues
- Прямые ссылки на GitHub

#### Workflow Runs
- Последние 5 запусков GitHub Actions
- Статусы выполнения (✓ success, ✗ failure, ⏱ in progress)
- Название workflow и номер запуска
- Дата и время запуска
- Ссылки на детали в GitHub

#### История SEO отчетов
- Последние 5 отчетов с датами
- Динамика SEO Score
- Ссылки на архивные отчеты

**Данные автоматически кэшируются на 5 минут для оптимизации производительности.**

---

## 🎨 Интерфейс

### Элементы управления

- **Вкладки** - переключение между разделами (SEO / Технические / Аналитика)
- **Выход** - выход из админ-панели (в правом верхнем углу)
- **Закрыть** - закрытие панели (кнопка ✕ или клавиша `Esc`)

### Цветовая схема

- **Фон:** Темная тема (slate-900)
- **Акценты:** Amber (желто-золотой)
- **Текст:** Белый/серый для контрастности
- **Индикаторы:** Зеленый для позитивных метрик

---

## 🔒 Безопасность

### Текущая реализация

- Базовая аутентификация по паролю
- Пароль хранится в переменных окружения
- Client-side проверка (подходит для MVP)

### Рекомендации для Production

Для повышения безопасности рекомендуется:

1. **Хэширование пароля**
   ```typescript
   // Используйте bcrypt или подобную библиотеку
   import bcrypt from 'bcryptjs';
   ```

2. **Server-side аутентификация**
   - Создать API route для авторизации
   - Использовать JWT токены
   - Добавить rate limiting

3. **Двухфакторная аутентификация (2FA)**
   - TOTP коды
   - Email/SMS верификация

4. **IP whitelist**
   - Ограничить доступ по IP
   - Настроить в Vercel/Cloudflare

### Пример улучшенной аутентификации

```typescript
// app/api/admin/auth/route.ts
import { NextRequest, NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';

export async function POST(req: NextRequest) {
  const { password } = await req.json();
  const hashedPassword = process.env.ADMIN_PASSWORD_HASH;

  const isValid = await bcrypt.compare(password, hashedPassword || '');

  if (isValid) {
    // Генерация JWT токена
    const token = generateJWT({ role: 'admin' });
    return NextResponse.json({ success: true, token });
  }

  return NextResponse.json({ success: false }, { status: 401 });
}
```

---

## 🔌 Интеграция с аналитическими сервисами

### Google Analytics

1. Получите Measurement ID (G-XXXXXXXXXX)
2. Добавьте в `.env.local`:
   ```env
   NEXT_PUBLIC_GA_ID=G-XXXXXXXXXX
   ```
3. Создайте API route для получения данных

### Yandex Metrika

1. Получите счетчик Метрики
2. Добавьте в `.env.local`:
   ```env
   NEXT_PUBLIC_YM_ID=XXXXXXXX
   ```
3. Используйте API Метрики для получения статистики

### MCP интеграция (будущее)

Для интеграции через Model Context Protocol:

```typescript
// lib/analytics/mcp-client.ts
export async function fetchAnalyticsData() {
  // Подключение к MCP серверу для получения данных
  const response = await fetch('/api/mcp/analytics');
  return response.json();
}
```

---

## 🛠️ Разработка и расширение

### Добавление новых метрик

1. Обновите интерфейс данных в `components/AdminPanel.tsx`:

```typescript
const seoData = {
  // ... существующие данные
  newMetric: {
    value: 123,
    change: '+5%'
  }
};
```

2. Добавьте отображение в UI:

```tsx
<div className="bg-slate-800/50 rounded-xl p-6">
  <h3>Новая метрика</h3>
  <div className="text-2xl font-bold">{seoData.newMetric.value}</div>
</div>
```

### Подключение реальных данных

Замените mock данные на API calls:

```typescript
import { useEffect, useState } from 'react';

const [seoData, setSeoData] = useState(null);

useEffect(() => {
  async function fetchData() {
    const response = await fetch('/api/analytics');
    const data = await response.json();
    setSeoData(data);
  }
  fetchData();
}, []);
```

---

## 📱 Адаптивность

Админ-панель полностью адаптивна:

- **Desktop:** Полноэкранное модальное окно с отступами
- **Tablet:** Адаптивная сетка (grid-cols-1 md:grid-cols-3)
- **Mobile:** Вертикальная прокрутка, стэк карточек

---

## 🐛 Troubleshooting

### Панель не открывается

1. Проверьте консоль браузера на ошибки
2. Убедитесь, что JavaScript включен
3. Попробуйте другую комбинацию клавиш (можно изменить в коде)

### Неверный пароль

1. Проверьте `.env.local` файл
2. Убедитесь, что переменная называется `ADMIN_PANEL_PASSWORD`
3. Перезапустите dev сервер после изменения .env

### Данные не отображаются

1. Проверьте что настроены переменные окружения для Google Analytics 4 или Yandex Metrika
2. Откройте DevTools (F12) → Console и проверьте нет ли ошибок
3. Проверьте сетевые запросы в DevTools → Network:
   - `/api/analytics/combined` должен возвращать `success: true`
   - `sources` должен содержать названия настроенных систем
4. Если `configured: false` - проверьте переменные окружения в Vercel
5. После изменения переменных окружения сделайте Redeploy в Vercel

---

## 🔌 API Endpoints

Админ-панель использует следующие API endpoints:

### `/api/analytics/google`
Получение данных из Google Analytics 4.

**Требуемые env variables:**
- `GA4_PROPERTY_ID`
- `GA4_CREDENTIALS`

**Возвращает:**
```json
{
  "success": true,
  "source": "google-analytics-4",
  "configured": true,
  "data": {
    "today": { "visits": 247, "pageviews": 892, ... },
    "week": { ... },
    "month": { ... },
    "topPages": [...],
    "sources": [...]
  }
}
```

### `/api/analytics/yandex`
Получение данных из Yandex Metrika.

**Требуемые env variables:**
- `YM_COUNTER_ID`
- `YM_ACCESS_TOKEN`

**Возвращает:**
```json
{
  "success": true,
  "source": "yandex-metrika",
  "configured": true,
  "data": { ... }
}
```

### `/api/analytics/combined`
Объединенные данные из обеих систем аналитики.

**Используется в AdminPanel** для вкладки "SEO & Аналитика".

**Возвращает:**
```json
{
  "success": true,
  "sources": ["Google Analytics 4", "Yandex Metrika"],
  "data": { ... },
  "raw": {
    "ga4": { ... },
    "yandex": { ... }
  }
}
```

### `/api/github/stats`
Статистика из GitHub Actions и Issues проекта seo_ai_models.

**Опциональные env variables:**
- `GITHUB_TOKEN` (для приватных репозиториев)

---

## 🔄 Roadmap

### ✅ Реализовано

- [x] Real-time данные из Google Analytics 4 API
- [x] Интеграция с Yandex Metrika API
- [x] Экспорт данных в CSV/JSON/Print
- [x] Уведомления о важных событиях
- [x] Графики и визуализации (Recharts)
- [x] Фильтры по датам и типам
- [x] GitHub Actions интеграция
- [x] SEO Score история и тренды

### Ближайшие улучшения

- [ ] PDF экспорт с красивым форматированием
- [ ] Push уведомления в браузере (Web Push)
- [ ] A/B тестирование метрик
- [ ] Сравнение с конкурентами
- [ ] Мобильное приложение (опционально)

### Продвинутые функции

- [ ] Управление контентом
- [ ] Редактирование страниц через UI
- [ ] Модерация комментариев/отзывов
- [ ] Email рассылки
- [ ] CRM интеграция
- [ ] Backup и restore данных

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте документацию
2. Изучите код в `components/AdminPanel.tsx`
3. Создайте issue в GitHub репозитории
4. Свяжитесь с разработчиком

---

## 📄 Лицензия

Часть проекта Legal AI PRO. См. основной [LICENSE](../LICENSE)

---

**Создано с ❤️ для Legal AI PRO**
