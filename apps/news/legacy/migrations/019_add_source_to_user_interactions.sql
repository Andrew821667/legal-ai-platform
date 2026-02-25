-- Migration 019: Add source field to user_interactions
-- Created: 2026-01-03
-- Description: Add source tracking for channel conversion analytics

-- Add source column to user_interactions
ALTER TABLE user_interactions
ADD COLUMN IF NOT EXISTS source VARCHAR(50);

-- Create index for source lookups
CREATE INDEX IF NOT EXISTS idx_user_interactions_source ON user_interactions(source);

-- Add comment
COMMENT ON COLUMN user_interactions.source IS 'Traffic source: channel, channel_article, web, app, direct, search';

-- Verification
SELECT 'source column added to user_interactions successfully!' as status;
