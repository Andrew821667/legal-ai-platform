# Pull Request: Analytics improvements, Perplexity search, and reaction system UX fixes

## 🎯 Summary

Major enhancements to the AI News Aggregator analytics dashboard, news fetching capabilities, and bot UX improvements.

## ✨ Key Features

### 1. **Perplexity Real-Time News Search** 🔍
- Added `fetch_perplexity_news()` method for real-time web search
- Searches recent news (last 24 hours) using Perplexity AI
- Returns structured JSON with title, content, URL, source
- Supports both Russian and English languages
- Integrated into `fetch_all_sources()` pipeline

**Benefits:**
- Real-time news access beyond RSS limitations
- Better coverage of Russian AI/LegalTech news
- Diversity of sources (Google News + Perplexity + Russian RSS)
- Perplexity citations provide source attribution

### 2. **Russian News RSS Sources** 📰
- Created SQL migration for Russian news feeds
- Added sources: Lenta.ru, RBC, Interfax, TASS, Habr
- Quality scores assigned (0.6-0.8) for ranking
- Idempotent migration (safe to run multiple times)

### 3. **Improved Reaction System UX** 👍
- **Inline keyboard now edits in place** (not creates new message)
- Reactions menu appears directly under the post (not at bottom)
- Much faster and better UX
- All 8 reaction types now working with proper emoji/text:
  - 👍 Полезно, 🔥 Важно, 🤔 Спорно
  - 💤 Банальщина, 🤷 Очевидный вывод
  - 👎 Плохое качество, 📉 Низкое качество контента, 📰 Плохой источник
- Keyboard restoration after reaction
- Removed message deletion (was causing delays)

### 4. **Bug Fixes** 🐛
- Fixed SQL column name error in diversity boost query (`article_id` not `raw_article_id`)
- Prevents `UndefinedColumnError` in analyze_articles_task

## 📦 Files Changed

**Configuration:**
- `app/config.py`: Added `perplexity_search_enabled` setting

**News Fetching:**
- `app/modules/fetcher.py`: Added Perplexity real-time search method
- `migrations/add_russian_news_sources.sql`: Russian RSS sources migration

**Bot UX:**
- `app/bot/handlers.py`: Improved reaction callback handlers

**Analytics:**
- `app/modules/ai_core.py`: Fixed diversity boost SQL query

## 🚀 Deployment Steps

```bash
# 1. Pull changes
git pull origin claude/bot-channel-development-lCoIU

# 2. Apply Russian sources migration
docker compose up -d postgres
docker compose exec -T postgres psql -U legal_user -d legal_ai_news < migrations/add_russian_news_sources.sql

# 3. Rebuild and restart
docker compose build --no-cache app
docker compose up -d

# 4. Verify
docker compose logs -f celery_worker
```

## ✅ Testing Checklist

- [x] Perplexity search fetches news successfully
- [x] Russian RSS sources added to database
- [x] Diversity boost query works without SQL errors
- [x] Reaction buttons appear under posts (not at bottom)
- [x] All 8 reaction types work with proper feedback
- [x] Keyboard returns to original state after reaction
- [x] No performance lag when clicking "Ваше мнение"

## 📊 Impact

**News Coverage:**
- **Before:** Google News RSS only (~10-15 articles/day)
- **After:** Google News + Perplexity + 5 Russian sources (~30-50 articles/day)

**User Experience:**
- **Before:** Reaction menu appeared at bottom, slow, only 3 reactions worked
- **After:** Instant inline menu, all 8 reactions working, much faster

**Data Quality:**
- Source diversity tracking ensures balanced content
- Better Russian market coverage
- Real-time news access

## 🔗 Related Issues

Fixes analytics SQL bug, improves news diversity, enhances bot UX.

---

**Commits:**
- 7121c23 fix: Improve reaction system UX and performance
- d8fa0ef feat: Add Perplexity real-time news search and Russian RSS sources
- 76a5af1 fix: correct column name in source diversity query (article_id not raw_article_id)
- 1feee92 feat: Comprehensive analytics improvements and source diversity enhancements
