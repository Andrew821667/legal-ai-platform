# 🔍 SEO AI Models - Автоматическая интеграция

## Обзор

Автоматический SEO анализ сайта с помощью [SEO AI Models](https://github.com/Andrew821667/seo-ai-models) через GitHub Actions.

## Что делает интеграция

✅ **Автоматический анализ**:
- Запускается каждое воскресенье в 03:00 UTC
- Анализирует все ключевые страницы сайта
- Оценивает SEO, контент и E-E-A-T метрики

✅ **Генерирует отчёты**:
- JSON отчёт с детальными метриками
- Markdown summary для быстрого просмотра
- Сохраняет в artifacts на 90 дней

✅ **Создаёт Issue**:
- Автоматически создаёт Issue с рекомендациями
- Отмечает критические проблемы
- Добавляет labels для фильтрации

## Настройка

### 1. GitHub Secrets

Добавь следующие secrets в настройках репозитория:

**Путь:** Settings → Secrets and variables → Actions → New repository secret

#### SERPAPI_KEY (опционально)
```
Получить: https://serpapi.com/
Бесплатный план: 100 запросов/месяц
```

#### OPENAI_API_KEY (опционально, для продвинутой аналитики)
```
Получить: https://platform.openai.com/api-keys
Стоимость: ~$0.50 за анализ
```

### 2. Обновить URL сайта

После деплоя замени URL в файле `.github/workflows/seo-analysis.yml`:

```python
# Строка 52
SITE_URL = "https://your-actual-domain.com"
```

### 3. Запустить вручную

1. Перейди в **Actions** → **Automatic SEO Analysis**
2. Нажми **Run workflow** → **Run workflow**
3. Дождись завершения (~5 минут)

## Как работает workflow

### Триггеры запуска

```yaml
# 1. По расписанию (каждое воскресенье в 03:00 UTC)
schedule:
  - cron: '0 3 * * 0'

# 2. Вручную через GitHub UI
workflow_dispatch:

# 3. После изменений в контенте
push:
  branches: [main]
  paths: ['app/**', 'components/**']
```

### Шаги выполнения

1. **Checkout repositories**
   - Клонирует сайт
   - Клонирует SEO AI Models

2. **Setup Python environment**
   - Устанавливает Python 3.11
   - Устанавливает зависимости
   - Устанавливает Playwright для JS сайтов

3. **Run analysis**
   - Анализирует все страницы
   - Вычисляет метрики
   - Генерирует рекомендации

4. **Save results**
   - Сохраняет JSON отчёт
   - Создаёт Markdown summary
   - Загружает в artifacts

5. **Create Issue** (при schedule)
   - Создаёт Issue с результатами
   - Добавляет top recommendations
   - Отмечает critical issues

## Структура отчёта

### JSON отчёт

```json
{
  "timestamp": "2025-01-11T03:00:00",
  "site_url": "https://legal-ai-pro.com",
  "overall_score": 87.5,
  "pages_analyzed": [
    {
      "url": "https://legal-ai-pro.com/",
      "score": 92.3,
      "seo": {
        "title": "✅ Присутствует",
        "meta_description": "✅ Оптимальная длина",
        "h1_count": 1,
        "mobile_friendly": true
      },
      "content": {
        "word_count": 1250,
        "readability_score": 68,
        "keyword_density": "оптимальная"
      },
      "eeat": {
        "expertise_signals": ["клиентские кейсы", "20+ лет опыта"],
        "trust_signals": ["контакты", "telegram bot"]
      }
    }
  ],
  "recommendations": [
    "Добавить structured data (Schema.org)",
    "Улучшить внутреннюю перелинковку",
    "Оптимизировать изображения (WebP)"
  ]
}
```

### Markdown Summary

```markdown
# SEO Analysis Report

**Date:** 2025-01-11 03:00:00
**Overall Score:** 87.5/100

## Pages Analyzed (6)

- [/](https://legal-ai-pro.com/) - Score: 92.3/100
- [/#features](https://legal-ai-pro.com/#features) - Score: 85.1/100
- [/#services](https://legal-ai-pro.com/#services) - Score: 88.7/100

## Top Recommendations

1. Добавить structured data (Schema.org)
2. Улучшить внутреннюю перелинковку
3. Оптимизировать изображения (WebP)
```

## Метрики анализа

### SEO Score (0-100)
- ✅ Title tags
- ✅ Meta descriptions
- ✅ Header hierarchy (H1-H6)
- ✅ Image alt texts
- ✅ Mobile-friendly
- ✅ Page speed
- ✅ HTTPS
- ✅ Canonical URLs

### Content Score (0-100)
- ✅ Word count
- ✅ Readability (Flesch-Kincaid)
- ✅ Keyword usage
- ✅ Semantic relevance
- ✅ Content structure
- ✅ Internal links

### E-E-A-T Score (0-100)
- ✅ Experience signals (кейсы, портфолио)
- ✅ Expertise signals (сертификаты, опыт)
- ✅ Authoritativeness (упоминания, ссылки)
- ✅ Trust signals (контакты, отзывы, SSL)

## Troubleshooting

### Workflow failed

**Проблема:** Workflow завершился с ошибкой

**Решение:**
1. Проверь логи в Actions
2. Убедись что URL сайта доступен
3. Проверь что API keys корректны

### Low scores

**Проблема:** Низкие scores по метрикам

**Решение:**
1. Прочитай recommendations в отчёте
2. Реализуй критические исправления
3. Запусти workflow повторно для проверки

### No Issue created

**Проблема:** Issue не создаётся автоматически

**Решение:**
1. Убедись что workflow запущен по schedule
2. Проверь права GitHub Actions: Settings → Actions → General → Workflow permissions → Read and write permissions

## Roadmap

### Ближайшие улучшения

- [ ] **Lighthouse integration** - Core Web Vitals
- [ ] **Competitor analysis** - сравнение с конкурентами
- [ ] **Keyword tracking** - отслеживание позиций
- [ ] **Automated fixes** - автоматические PR с исправлениями
- [ ] **Slack/Telegram notifications** - уведомления в мессенджеры

### Продвинутые возможности

- [ ] **A/B testing** - тестирование SEO изменений
- [ ] **Historical trends** - графики изменения метрик
- [ ] **Custom rules** - кастомные правила анализа
- [ ] **Multi-language support** - поддержка мультиязычности

## Полезные ссылки

- [SEO AI Models Repository](https://github.com/Andrew821667/seo-ai-models)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [E-E-A-T Guidelines](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
- [Core Web Vitals](https://web.dev/vitals/)

---

**Вопросы?** Создай Issue или напиши в [Telegram](https://t.me/legal_ai_helper_new_bot)
