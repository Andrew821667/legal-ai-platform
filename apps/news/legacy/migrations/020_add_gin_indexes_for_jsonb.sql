-- Migration 020: Add GIN indexes for JSONB fields
-- Created: 2026-01-03
-- Description: Add GIN indexes for faster JSONB queries on reactions fields

-- GIN index for publications.reactions
CREATE INDEX IF NOT EXISTS idx_publications_reactions_gin
ON publications USING GIN(reactions);

-- GIN index for post_analytics.reactions
CREATE INDEX IF NOT EXISTS idx_post_analytics_reactions_gin
ON post_analytics USING GIN(reactions);

-- GIN index for system_logs.context
CREATE INDEX IF NOT EXISTS idx_system_logs_context_gin
ON system_logs USING GIN(context);

-- Comments
COMMENT ON INDEX idx_publications_reactions_gin IS 'GIN index for fast JSONB reactions queries';
COMMENT ON INDEX idx_post_analytics_reactions_gin IS 'GIN index for fast JSONB reactions queries in analytics';
COMMENT ON INDEX idx_system_logs_context_gin IS 'GIN index for fast JSONB context queries in logs';

-- Verification
SELECT 'GIN indexes added successfully!' as status;
