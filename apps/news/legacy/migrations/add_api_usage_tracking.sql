-- Добавление таблиц для отслеживания стоимости API
-- Выполнить: cat migrations/add_api_usage_tracking.sql | docker compose exec -T postgres psql -U legal_user -d legal_ai_news

-- Таблица для детальной статистики использования API
CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,  -- openai, perplexity
    model VARCHAR(100) NOT NULL,    -- gpt-4o-mini, sonar, etc
    operation VARCHAR(100),          -- ranking, draft_generation, editing, etc

    -- Токены
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,

    -- Стоимость в USD (до 6 знаков после запятой для точности)
    cost_usd NUMERIC(10, 6) DEFAULT 0.0,

    -- Связи с другими таблицами
    article_id INTEGER REFERENCES raw_articles(id) ON DELETE SET NULL,
    draft_id INTEGER REFERENCES post_drafts(id) ON DELETE SET NULL,

    -- Временные метки
    created_at TIMESTAMP DEFAULT NOW(),
    date DATE DEFAULT CURRENT_DATE
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_api_usage_provider ON api_usage(provider);
CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(date);
CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_api_usage_article_id ON api_usage(article_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_draft_id ON api_usage(draft_id);

-- Таблица для агрегированной статистики по месяцам
CREATE TABLE IF NOT EXISTS monthly_api_stats (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,  -- 1-12
    provider VARCHAR(50) NOT NULL,

    total_requests INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(10, 2) DEFAULT 0.0,

    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(year, month, provider)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_monthly_stats_year_month ON monthly_api_stats(year, month);
CREATE INDEX IF NOT EXISTS idx_monthly_stats_provider ON monthly_api_stats(provider);

-- Комментарии
COMMENT ON TABLE api_usage IS 'Детальная статистика использования AI API (OpenAI, Perplexity)';
COMMENT ON TABLE monthly_api_stats IS 'Агрегированная статистика API по месяцам';

COMMENT ON COLUMN api_usage.cost_usd IS 'Стоимость в USD с точностью до 6 знаков после запятой';
COMMENT ON COLUMN api_usage.operation IS 'Тип операции: ranking, draft_generation, editing, etc';

-- Проверка
SELECT 'api_usage table created' as status;
SELECT 'monthly_api_stats table created' as status;
