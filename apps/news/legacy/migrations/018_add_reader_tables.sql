-- Migration 018: Add Reader Bot Tables
-- Created: 2026-01-03
-- Description: Tables for reader bot personalization and engagement

-- 1. User profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    full_name VARCHAR(255),

    -- Onboarding data
    topics TEXT[],                    -- ['gdpr', 'ai_law', 'crypto', 'corporate', 'tax', 'ip']
    expertise_level VARCHAR(50),      -- 'student', 'lawyer', 'in_house', 'business'
    digest_frequency VARCHAR(20),     -- 'daily', 'twice_week', 'weekly', 'never'

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,

    -- Stats
    total_articles_viewed INTEGER DEFAULT 0,
    total_feedback_given INTEGER DEFAULT 0
);

-- 2. User feedback on articles
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    publication_id INT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,

    -- Feedback data
    is_useful BOOLEAN NOT NULL,           -- TRUE = 👍, FALSE = 👎
    feedback_type VARCHAR(50),            -- 'too_complex', 'not_relevant', 'outdated', 'shallow', etc.

    created_at TIMESTAMP DEFAULT NOW(),

    -- Ensure one feedback per user per article
    UNIQUE(user_id, publication_id)
);

-- 3. User interactions (tracking engagement)
CREATE TABLE IF NOT EXISTS user_interactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    publication_id INT REFERENCES publications(id) ON DELETE CASCADE,

    -- Interaction type
    action VARCHAR(50) NOT NULL,      -- 'view', 'save', 'share', 'search', 'digest_open'

    -- Optional metadata
    search_query TEXT,                -- For 'search' actions

    created_at TIMESTAMP DEFAULT NOW()
);

-- 4. Saved articles (bookmarks)
CREATE TABLE IF NOT EXISTS saved_articles (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    publication_id INT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,

    created_at TIMESTAMP DEFAULT NOW(),

    -- Ensure no duplicates
    UNIQUE(user_id, publication_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_feedback_user ON user_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_publication ON user_feedback(publication_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_created ON user_feedback(created_at);

CREATE INDEX IF NOT EXISTS idx_user_interactions_user ON user_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_publication ON user_interactions(publication_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_action ON user_interactions(action);
CREATE INDEX IF NOT EXISTS idx_user_interactions_created ON user_interactions(created_at);

CREATE INDEX IF NOT EXISTS idx_saved_articles_user ON saved_articles(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_articles_publication ON saved_articles(publication_id);

CREATE INDEX IF NOT EXISTS idx_user_profiles_active ON user_profiles(is_active);
CREATE INDEX IF NOT EXISTS idx_user_profiles_digest ON user_profiles(digest_frequency) WHERE digest_frequency != 'never';

-- Comments for documentation
COMMENT ON TABLE user_profiles IS 'Reader bot user profiles with preferences and onboarding data';
COMMENT ON TABLE user_feedback IS 'User feedback (like/dislike) on published articles';
COMMENT ON TABLE user_interactions IS 'Tracking user engagement (views, searches, shares)';
COMMENT ON TABLE saved_articles IS 'User bookmarked articles';

COMMENT ON COLUMN user_profiles.topics IS 'Array of interested topics: gdpr, ai_law, crypto, corporate, tax, ip';
COMMENT ON COLUMN user_profiles.expertise_level IS 'User expertise: student, lawyer, in_house, business';
COMMENT ON COLUMN user_profiles.digest_frequency IS 'Digest frequency: daily, twice_week, weekly, never';
