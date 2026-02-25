-- Add scored_at column to raw_articles table
-- This column tracks when AI last scored the article

ALTER TABLE raw_articles
ADD COLUMN IF NOT EXISTS scored_at TIMESTAMP WITHOUT TIME ZONE;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_raw_articles_scored_at ON raw_articles(scored_at);

COMMENT ON COLUMN raw_articles.scored_at IS 'Время последней оценки AI';
