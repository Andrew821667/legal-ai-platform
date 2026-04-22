# 🔍 Инструкция по переиндексации сайта в Google

## Проблема
Google индексирует старый домен Vercel (`legal-ai-website-iota.vercel.app`) вместо нового домена `ai-verdict.ru`.

## ✅ Что уже исправлено в коде

1. ✅ Создан `app/robots.ts` - динамический robots.txt
2. ✅ Создан `app/sitemap.ts` - динамическая карта сайта
3. ✅ Добавлены canonical URLs в metadata
4. ✅ Настроены 301 редиректы со старого Vercel домена на новый
5. ✅ Добавлены Open Graph метатеги
6. ✅ Добавлены keywords и расширенная metadata

## 📋 Что нужно сделать вручную

### 1. Настроить переменные окружения в Vercel

Зайдите в настройки проекта Vercel:
```
Settings → Environment Variables
```

Добавьте:
```bash
NEXT_PUBLIC_SITE_URL=https://ai-verdict.ru
```

Пересоберите проект после добавления переменной.

---

### 2. Google Search Console - Добавить новый домен

#### Шаг 1: Добавить property для ai-verdict.ru
1. Откройте [Google Search Console](https://search.google.com/search-console)
2. Нажмите "Add Property"
3. Выберите "URL prefix"
4. Введите: `https://ai-verdict.ru`
5. Подтвердите владение одним из способов:
   - **DNS verification** (рекомендуется):
     - Добавьте TXT запись в DNS вашего домена
     - Код верификации будет показан в Search Console
   - **HTML file upload**:
     - Скачайте файл верификации
     - Загрузите в `public/` папку вашего проекта
   - **HTML tag** (самый простой):
     - Скопируйте meta tag
     - Добавьте в `app/layout.tsx` в секцию `verification`:
       ```typescript
       verification: {
         google: 'your-verification-code-here',
       }
       ```

#### Шаг 2: Отправить sitemap
После подтверждения владения:
1. Перейдите в раздел **Sitemaps**
2. Введите: `https://ai-verdict.ru/sitemap.xml`
3. Нажмите **Submit**

---

### 3. Удалить старый Vercel домен из индекса

#### Вариант A: Через Google Search Console (если есть доступ)
1. Откройте старый property (`legal-ai-website-iota.vercel.app`)
2. Перейдите в **Removals**
3. Нажмите **New Request**
4. Выберите **Temporarily remove URL**
5. Введите: `https://legal-ai-website-iota.vercel.app/`
6. Выберите **Remove all URLs with this prefix**

#### Вариант B: Добавить noindex на старом домене (если нет доступа к GSC)
1. В настройках Vercel отключите старый deployment или добавьте:
   ```typescript
   // В next.config.js добавить header для старого домена
   {
     source: '/:path*',
     has: [{ type: 'host', value: '*.vercel.app' }],
     headers: [{ key: 'X-Robots-Tag', value: 'noindex, nofollow' }],
   }
   ```

---

### 4. Запросить переиндексацию новых страниц

После деплоя изменений:

1. Откройте [Google Search Console](https://search.google.com/search-console) для `ai-verdict.ru`
2. Используйте **URL Inspection** tool
3. Проверьте URL: `https://ai-verdict.ru`
4. Нажмите **Request Indexing**
5. Повторите для важных страниц:
   - `https://ai-verdict.ru/#features`
   - `https://ai-verdict.ru/#calculator`
   - `https://ai-verdict.ru/#services`

---

### 5. Yandex.Webmaster (для российской аудитории)

1. Откройте [Yandex.Webmaster](https://webmaster.yandex.ru)
2. Добавьте сайт `https://ai-verdict.ru`
3. Подтвердите владение (meta tag или DNS)
4. Отправьте sitemap: `https://ai-verdict.ru/sitemap.xml`
5. В разделе "Индексирование" → "Переобход страниц" отправьте главную страницу

---

### 6. Проверить редиректы

Убедитесь что старый домен редиректит на новый:

```bash
# Проверка редиректа
curl -I https://legal-ai-website-iota.vercel.app

# Должен вернуть:
# HTTP/2 301
# location: https://ai-verdict.ru/
```

Если редирект не работает - убедитесь что изменения в `next.config.js` задеплоены на Vercel.

---

### 7. Мониторинг переиндексации

Google переиндексирует сайт в течение **1-4 недель**. Следите за прогрессом:

1. **Google Search Console** → Coverage
   - Смотрите количество проиндексированных страниц
   - Проверяйте на ошибки

2. **Search в Google**:
   ```
   site:ai-verdict.ru
   ```
   Должен показывать новый сайт

3. **Проверка старого домена**:
   ```
   site:legal-ai-website-iota.vercel.app
   ```
   Результаты должны исчезнуть через несколько недель

---

## 🚀 Ускорение индексации

### Внешние ссылки
Создайте ссылки на новый сайт:
- Social media профили (Telegram, LinkedIn, Facebook)
- Business listings (Google My Business, Yandex.Business)
- Отраслевые каталоги

### Контент
- Опубликуйте несколько статей/кейсов на сайте
- Добавьте структурированные данные (schema.org)

### Sitemap ping
Уведомите поисковики о новой sitemap:
```bash
# Google
https://www.google.com/ping?sitemap=https://ai-verdict.ru/sitemap.xml

# Yandex
https://webmaster.yandex.ru/ping?sitemap=https://ai-verdict.ru/sitemap.xml
```

---

## 📊 Проверка SEO метатегов

После деплоя проверьте что все метатеги корректны:

1. Откройте `https://ai-verdict.ru`
2. View Page Source (Ctrl+U)
3. Проверьте наличие:
   - `<link rel="canonical" href="https://ai-verdict.ru/" />`
   - `<meta property="og:url" content="https://ai-verdict.ru/" />`
   - `<meta name="robots" content="index, follow" />`

Или используйте инструменты:
- [Google Rich Results Test](https://search.google.com/test/rich-results)
- [Facebook Sharing Debugger](https://developers.facebook.com/tools/debug/)
- [Twitter Card Validator](https://cards-dev.twitter.com/validator)

---

## ⏱️ Ожидаемые сроки

- **Sitemap обработка**: 1-3 дня
- **Первая индексация**: 3-7 дней
- **Полная переиндексация**: 2-4 недели
- **Удаление старого домена**: 4-8 недель

---

## 🔔 Важно!

После выполнения всех шагов НЕ УДАЛЯЙТЕ старый Vercel deployment сразу!
Оставьте редирект работать минимум 2-3 месяца для передачи SEO-веса.

Только после того как:
1. Новый домен полностью проиндексирован
2. Старый домен удален из индекса Google
3. Трафик полностью перешел на новый домен

Можно будет удалить старый deployment.

---

## 📞 Поддержка

Если возникнут проблемы, проверьте:
- Google Search Console → Coverage → Errors
- Google Search Console → URL Inspection
- Логи в Vercel Dashboard

Индексация - медленный процесс, наберитесь терпения! 🚀
