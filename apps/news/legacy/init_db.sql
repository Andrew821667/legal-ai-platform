-- AI-News Aggregator for LegalTech Database Schema
-- PostgreSQL 15+ initialization script

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For similarity search

-- ====================
-- Table: raw_articles
-- ====================
CREATE TABLE IF NOT EXISTS raw_articles (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    source_name VARCHAR(100) NOT NULL,
    published_at TIMESTAMP,
    fetched_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'new',
    relevance_score FLOAT,
    CONSTRAINT chk_status CHECK (status IN ('new', 'filtered', 'processed', 'rejected'))
);

CREATE INDEX idx_raw_articles_status ON raw_articles(status);
CREATE INDEX idx_raw_articles_fetched ON raw_articles(fetched_at DESC);
CREATE INDEX idx_raw_articles_source ON raw_articles(source_name);
CREATE INDEX idx_raw_articles_url_hash ON raw_articles USING hash(url);

COMMENT ON TABLE raw_articles IS 'Сырые статьи из RSS и других источников';
COMMENT ON COLUMN raw_articles.status IS 'new - новая, filtered - прошла фильтр, processed - обработана AI, rejected - отклонена';

-- ====================
-- Table: legal_knowledge
-- ====================
CREATE TABLE IF NOT EXISTS legal_knowledge (
    id SERIAL PRIMARY KEY,
    doc_name VARCHAR(200) NOT NULL,
    article_number VARCHAR(50),
    text_chunk TEXT NOT NULL,
    keywords TEXT[],
    ts_vector tsvector GENERATED ALWAYS AS (to_tsvector('russian', text_chunk)) STORED
);

CREATE INDEX idx_legal_ts_vector ON legal_knowledge USING GIN(ts_vector);
CREATE INDEX idx_legal_keywords ON legal_knowledge USING GIN(keywords);
CREATE INDEX idx_legal_doc_name ON legal_knowledge(doc_name);

COMMENT ON TABLE legal_knowledge IS 'База знаний юридических документов для RAG';
COMMENT ON COLUMN legal_knowledge.ts_vector IS 'Full-text search vector для поиска по содержимому';

-- ====================
-- Table: post_drafts
-- ====================
CREATE TABLE IF NOT EXISTS post_drafts (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES raw_articles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    legal_context TEXT,
    image_path TEXT,
    audio_path TEXT,
    confidence_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,
    reviewed_by INTEGER,
    status VARCHAR(20) DEFAULT 'pending_review',
    rejection_reason TEXT,
    CONSTRAINT chk_draft_status CHECK (status IN ('pending_review', 'approved', 'rejected', 'edited'))
);

CREATE INDEX idx_drafts_status ON post_drafts(status);
CREATE INDEX idx_drafts_created ON post_drafts(created_at DESC);
CREATE INDEX idx_drafts_article_id ON post_drafts(article_id);

COMMENT ON TABLE post_drafts IS 'Драфты постов для модерации';
COMMENT ON COLUMN post_drafts.status IS 'pending_review - ожидает модерации, approved - одобрен, rejected - отклонен, edited - отредактирован';

-- ====================
-- Table: publications
-- ====================
CREATE TABLE IF NOT EXISTS publications (
    id SERIAL PRIMARY KEY,
    draft_id INTEGER REFERENCES post_drafts(id) ON DELETE CASCADE,
    message_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    published_at TIMESTAMP DEFAULT NOW(),
    views INTEGER DEFAULT 0,
    reactions JSONB DEFAULT '{}',
    forwards INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0
);

CREATE INDEX idx_publications_draft_id ON publications(draft_id);
CREATE INDEX idx_publications_published ON publications(published_at DESC);
CREATE INDEX idx_publications_message_id ON publications(message_id);

COMMENT ON TABLE publications IS 'Опубликованные посты в Telegram канале';

-- ====================
-- Table: post_analytics
-- ====================
CREATE TABLE IF NOT EXISTS post_analytics (
    id SERIAL PRIMARY KEY,
    publication_id INTEGER REFERENCES publications(id) ON DELETE CASCADE,
    views INTEGER DEFAULT 0,
    reactions JSONB DEFAULT '{}',
    utm_clicks INTEGER DEFAULT 0,
    avg_read_time INTEGER,
    collected_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_analytics_publication_id ON post_analytics(publication_id);
CREATE INDEX idx_analytics_collected ON post_analytics(collected_at DESC);

COMMENT ON TABLE post_analytics IS 'Аналитика по опубликованным постам';
COMMENT ON COLUMN post_analytics.avg_read_time IS 'Среднее время чтения в секундах';

-- ====================
-- Table: feedback_labels
-- ====================
CREATE TABLE IF NOT EXISTS feedback_labels (
    id SERIAL PRIMARY KEY,
    draft_id INTEGER REFERENCES post_drafts(id) ON DELETE CASCADE,
    admin_action VARCHAR(20) NOT NULL,
    rejection_reason TEXT,
    performance_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT chk_admin_action CHECK (admin_action IN ('published', 'rejected', 'edited'))
);

CREATE INDEX idx_feedback_draft_id ON feedback_labels(draft_id);
CREATE INDEX idx_feedback_created ON feedback_labels(created_at DESC);

COMMENT ON TABLE feedback_labels IS 'Обучающие данные для ML (feedback loop)';
COMMENT ON COLUMN feedback_labels.performance_score IS 'Оценка качества поста после публикации';

-- ====================
-- Table: sources
-- ====================
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    url TEXT NOT NULL,
    type VARCHAR(20) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    last_fetch TIMESTAMP,
    fetch_errors INTEGER DEFAULT 0,
    quality_score FLOAT DEFAULT 0.5,
    CONSTRAINT chk_source_type CHECK (type IN ('rss', 'web', 'telegram'))
);

CREATE INDEX idx_sources_enabled ON sources(enabled);
CREATE INDEX idx_sources_quality ON sources(quality_score DESC);

COMMENT ON TABLE sources IS 'Управление источниками новостей';
COMMENT ON COLUMN sources.quality_score IS 'Оценка качества источника (0.0 - 1.0)';

-- ====================
-- Table: system_logs
-- ====================
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    level VARCHAR(10) NOT NULL,
    message TEXT NOT NULL,
    context JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT chk_log_level CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'))
);

CREATE INDEX idx_logs_created ON system_logs(created_at DESC);
CREATE INDEX idx_logs_level ON system_logs(level);
CREATE INDEX idx_logs_context ON system_logs USING GIN(context);

COMMENT ON TABLE system_logs IS 'Системные логи приложения';

-- ====================
-- Table: media_files
-- ====================
CREATE TABLE IF NOT EXISTS media_files (
    id SERIAL PRIMARY KEY,
    draft_id INTEGER REFERENCES post_drafts(id) ON DELETE CASCADE,
    file_type VARCHAR(10) NOT NULL,
    file_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT chk_file_type CHECK (file_type IN ('image', 'audio'))
);

CREATE INDEX idx_media_draft_id ON media_files(draft_id);
CREATE INDEX idx_media_type ON media_files(file_type);

COMMENT ON TABLE media_files IS 'Медиа файлы (обложки, аудио)';

-- ====================
-- Initial Data
-- ====================

-- Default sources
INSERT INTO sources (name, url, type, enabled) VALUES
    ('Google News RSS RU', 'https://news.google.com/rss/search?q=искусственный+интеллект+право&hl=ru&gl=RU&ceid=RU:ru', 'rss', true),
    ('Google News RSS EN', 'https://news.google.com/rss/search?q=artificial+intelligence+law&hl=en&gl=US&ceid=US:en', 'rss', true)
ON CONFLICT (name) DO NOTHING;

-- ====================
-- Utility Functions
-- ====================

-- Function to calculate article similarity
CREATE OR REPLACE FUNCTION calculate_similarity(text1 TEXT, text2 TEXT)
RETURNS FLOAT AS $$
BEGIN
    RETURN similarity(text1, text2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION calculate_similarity IS 'Вычисляет схожесть двух текстов (0.0 - 1.0)';

-- Function to log system events
CREATE OR REPLACE FUNCTION log_event(
    p_level VARCHAR(10),
    p_message TEXT,
    p_context JSONB DEFAULT '{}'
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO system_logs (level, message, context)
    VALUES (p_level, p_message, p_context);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION log_event IS 'Записывает событие в системный лог';

-- Function to cleanup old logs
CREATE OR REPLACE FUNCTION cleanup_old_logs(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM system_logs
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_logs IS 'Удаляет старые логи (по умолчанию старше 90 дней)';

-- Function to get source quality statistics
CREATE OR REPLACE FUNCTION get_source_stats()
RETURNS TABLE (
    source_name VARCHAR(100),
    total_articles BIGINT,
    processed_articles BIGINT,
    published_articles BIGINT,
    quality_rate FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.name,
        COUNT(DISTINCT ra.id) as total_articles,
        COUNT(DISTINCT CASE WHEN ra.status = 'processed' THEN ra.id END) as processed_articles,
        COUNT(DISTINCT p.id) as published_articles,
        CASE
            WHEN COUNT(DISTINCT ra.id) > 0
            THEN CAST(COUNT(DISTINCT p.id) AS FLOAT) / COUNT(DISTINCT ra.id)
            ELSE 0.0
        END as quality_rate
    FROM sources s
    LEFT JOIN raw_articles ra ON ra.source_name = s.name
    LEFT JOIN post_drafts pd ON pd.article_id = ra.id
    LEFT JOIN publications p ON p.draft_id = pd.id
    GROUP BY s.name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_source_stats IS 'Возвращает статистику по источникам';

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO legal_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO legal_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO legal_user;

-- Database initialization completed
SELECT 'Database schema initialized successfully!' as status;
