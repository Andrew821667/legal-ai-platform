-- Migration 021: Add Lead Profiles Table
-- Created: 2026-01-04
-- Description: Extended profiles for qualified leads with contact information and qualification data

-- Lead profiles table
CREATE TABLE IF NOT EXISTS lead_profiles (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,

    -- Contact Information (Lead Magnet)
    email VARCHAR(255),
    phone VARCHAR(50),
    company VARCHAR(255),
    position VARCHAR(255),

    -- Lead Qualification
    lead_status VARCHAR(50) DEFAULT 'interested',  -- 'interested', 'qualified', 'converted', 'nurturing'
    expertise_level VARCHAR(50),                    -- 'beginner', 'intermediate', 'expert', 'business_owner'
    business_focus VARCHAR(100),                    -- 'law_firm', 'corporate', 'startup', 'consulting', 'other'

    -- Lead Magnet Specific
    lead_magnet_completed BOOLEAN DEFAULT FALSE,   -- True if completed lead magnet flow
    questions_asked INTEGER DEFAULT 0,             -- How many questions asked in lead magnet
    digest_requested BOOLEAN DEFAULT FALSE,        -- True if requested personalized digest

    -- Lead Scoring
    lead_score INTEGER DEFAULT 0,                  -- 0-100 score based on engagement and qualification
    last_lead_activity TIMESTAMP DEFAULT NOW(),

    -- Additional Business Info
    pain_points TEXT[],                           -- What problems they want to solve
    budget_range VARCHAR(50),                     -- 'under_100k', '100k_500k', '500k_1m', 'over_1m'
    timeline VARCHAR(50),                         -- 'immediate', '3_months', '6_months', '1_year', 'researching'

    -- CRM Integration
    crm_id VARCHAR(100),                          -- External CRM system ID
    sales_notes TEXT,                             -- Notes for sales team

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    UNIQUE(user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_lead_profiles_user_id ON lead_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_lead_profiles_status ON lead_profiles(lead_status);
CREATE INDEX IF NOT EXISTS idx_lead_profiles_expertise ON lead_profiles(expertise_level);
CREATE INDEX IF NOT EXISTS idx_lead_profiles_score ON lead_profiles(lead_score);
CREATE INDEX IF NOT EXISTS idx_lead_profiles_completed ON lead_profiles(lead_magnet_completed);
CREATE INDEX IF NOT EXISTS idx_lead_profiles_created ON lead_profiles(created_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_lead_profile_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for automatic updated_at
CREATE TRIGGER trigger_lead_profiles_updated_at
    BEFORE UPDATE ON lead_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_lead_profile_updated_at();

-- Comments for documentation
COMMENT ON TABLE lead_profiles IS 'Extended profiles for qualified leads with contact information and qualification data';
COMMENT ON COLUMN lead_profiles.user_id IS 'Reference to user_profiles.user_id';
COMMENT ON COLUMN lead_profiles.lead_status IS 'Lead qualification status: interested, qualified, converted, nurturing';
COMMENT ON COLUMN lead_profiles.expertise_level IS 'User expertise level: beginner, intermediate, expert, business_owner';
COMMENT ON COLUMN lead_profiles.business_focus IS 'Business focus area: law_firm, corporate, startup, consulting, other';
COMMENT ON COLUMN lead_profiles.lead_magnet_completed IS 'Whether user completed lead magnet flow (contacts + questions)';
COMMENT ON COLUMN lead_profiles.lead_score IS 'Lead scoring 0-100 based on engagement and qualification';
COMMENT ON COLUMN lead_profiles.pain_points IS 'Array of business problems user wants to solve';
COMMENT ON COLUMN lead_profiles.budget_range IS 'Budget range for solutions: under_100k, 100k_500k, 500k_1m, over_1m';
COMMENT ON COLUMN lead_profiles.timeline IS 'Implementation timeline: immediate, 3_months, 6_months, 1_year, researching';