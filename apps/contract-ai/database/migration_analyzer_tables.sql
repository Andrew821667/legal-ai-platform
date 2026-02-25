-- Contract Analyzer Tables
-- Tables for storing detailed analysis results, risks, recommendations, and suggested changes

-- ===================================================
-- 1. CONTRACT RISKS
-- ===================================================
CREATE TABLE IF NOT EXISTS contract_risks (
    id SERIAL PRIMARY KEY,
    contract_id INTEGER REFERENCES contracts(id) ON DELETE CASCADE,
    analysis_id INTEGER REFERENCES analysis_results(id) ON DELETE CASCADE,

    -- Risk classification
    risk_type VARCHAR(50) NOT NULL,  -- financial, legal, operational, reputational
    severity VARCHAR(20) NOT NULL,   -- critical, significant, minor
    probability VARCHAR(20),          -- high, medium, low

    -- Risk details
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    consequences TEXT,                -- qualitative assessment (no monetary)

    -- Location in document
    xpath_location TEXT,
    section_name VARCHAR(255),

    -- RAG sources
    rag_sources JSONB DEFAULT '[]',  -- sources from RAG (precedents, norms, analogues)

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_risk_type CHECK (risk_type IN ('financial', 'legal', 'operational', 'reputational')),
    CONSTRAINT check_severity CHECK (severity IN ('critical', 'significant', 'minor')),
    CONSTRAINT check_probability CHECK (probability IN ('high', 'medium', 'low', NULL))
);

CREATE INDEX IF NOT EXISTS idx_contract_risks_contract_id ON contract_risks(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_risks_analysis_id ON contract_risks(analysis_id);
CREATE INDEX IF NOT EXISTS idx_contract_risks_severity ON contract_risks(severity);
CREATE INDEX IF NOT EXISTS idx_contract_risks_type ON contract_risks(risk_type);

-- ===================================================
-- 2. CONTRACT RECOMMENDATIONS
-- ===================================================
CREATE TABLE IF NOT EXISTS contract_recommendations (
    id SERIAL PRIMARY KEY,
    contract_id INTEGER REFERENCES contracts(id) ON DELETE CASCADE,
    analysis_id INTEGER REFERENCES analysis_results(id) ON DELETE CASCADE,

    -- Recommendation classification
    category VARCHAR(100) NOT NULL,  -- legal_compliance, financial_optimization, risk_mitigation, etc.
    priority VARCHAR(20) NOT NULL,   -- critical, high, medium, low

    -- Recommendation details
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    reasoning TEXT,                   -- why this recommendation
    expected_benefit TEXT,            -- expected outcome

    -- Related risk
    related_risk_id INTEGER REFERENCES contract_risks(id) ON DELETE SET NULL,

    -- Implementation
    implementation_complexity VARCHAR(20),  -- easy, medium, hard

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_priority CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    CONSTRAINT check_complexity CHECK (implementation_complexity IN ('easy', 'medium', 'hard', NULL))
);

CREATE INDEX IF NOT EXISTS idx_contract_recommendations_contract_id ON contract_recommendations(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_recommendations_analysis_id ON contract_recommendations(analysis_id);
CREATE INDEX IF NOT EXISTS idx_contract_recommendations_priority ON contract_recommendations(priority);
CREATE INDEX IF NOT EXISTS idx_contract_recommendations_category ON contract_recommendations(category);

-- ===================================================
-- 3. CONTRACT ANNOTATIONS
-- ===================================================
CREATE TABLE IF NOT EXISTS contract_annotations (
    id SERIAL PRIMARY KEY,
    contract_id INTEGER REFERENCES contracts(id) ON DELETE CASCADE,
    analysis_id INTEGER REFERENCES analysis_results(id) ON DELETE CASCADE,

    -- Location
    xpath_location TEXT NOT NULL,
    section_name VARCHAR(255),

    -- Annotation details
    annotation_type VARCHAR(50) NOT NULL,  -- risk, warning, info, suggestion
    content TEXT NOT NULL,

    -- Related entities
    related_risk_id INTEGER REFERENCES contract_risks(id) ON DELETE SET NULL,
    related_recommendation_id INTEGER REFERENCES contract_recommendations(id) ON DELETE SET NULL,

    -- Visual highlighting
    highlight_color VARCHAR(20),  -- red, yellow, green

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_annotation_type CHECK (annotation_type IN ('risk', 'warning', 'info', 'suggestion')),
    CONSTRAINT check_highlight_color CHECK (highlight_color IN ('red', 'yellow', 'green', NULL))
);

CREATE INDEX IF NOT EXISTS idx_contract_annotations_contract_id ON contract_annotations(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_annotations_analysis_id ON contract_annotations(analysis_id);
CREATE INDEX IF NOT EXISTS idx_contract_annotations_type ON contract_annotations(annotation_type);

-- ===================================================
-- 4. CONTRACT SUGGESTED CHANGES
-- ===================================================
CREATE TABLE IF NOT EXISTS contract_suggested_changes (
    id SERIAL PRIMARY KEY,
    contract_id INTEGER REFERENCES contracts(id) ON DELETE CASCADE,
    analysis_id INTEGER REFERENCES analysis_results(id) ON DELETE CASCADE,

    -- Location
    xpath_location TEXT NOT NULL,
    section_name VARCHAR(255),

    -- Change details
    original_text TEXT NOT NULL,
    suggested_text TEXT NOT NULL,
    change_type VARCHAR(50),          -- addition, modification, deletion, clarification

    -- Reasoning
    issue TEXT NOT NULL,              -- what's the problem
    reasoning TEXT NOT NULL,          -- why this change
    legal_basis TEXT,                 -- references to laws, articles

    -- Related entities
    related_risk_id INTEGER REFERENCES contract_risks(id) ON DELETE SET NULL,
    related_recommendation_id INTEGER REFERENCES contract_recommendations(id) ON DELETE SET NULL,

    -- Approval workflow
    status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, rejected, modified
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP,
    rejection_reason TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_change_type CHECK (change_type IN ('addition', 'modification', 'deletion', 'clarification', NULL)),
    CONSTRAINT check_status CHECK (status IN ('pending', 'approved', 'rejected', 'modified'))
);

CREATE INDEX IF NOT EXISTS idx_contract_suggested_changes_contract_id ON contract_suggested_changes(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_suggested_changes_analysis_id ON contract_suggested_changes(analysis_id);
CREATE INDEX IF NOT EXISTS idx_contract_suggested_changes_status ON contract_suggested_changes(status);

-- ===================================================
-- 5. ANALYSIS FEEDBACK
-- ===================================================
CREATE TABLE IF NOT EXISTS analysis_feedback (
    id SERIAL PRIMARY KEY,
    analysis_id INTEGER REFERENCES analysis_results(id) ON DELETE CASCADE,
    contract_id INTEGER REFERENCES contracts(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- Overall feedback
    overall_rating INTEGER CHECK (overall_rating >= 1 AND overall_rating <= 5),

    -- Specific feedback
    missed_risks TEXT[],              -- risks that were missed
    false_positives TEXT[],           -- risks that were incorrectly identified

    -- Quality assessment
    recommendations_quality INTEGER CHECK (recommendations_quality >= 1 AND recommendations_quality <= 5),
    suggested_changes_quality INTEGER CHECK (suggested_changes_quality >= 1 AND suggested_changes_quality <= 5),

    -- Comments
    positive_aspects TEXT,
    areas_for_improvement TEXT,
    additional_comments TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_feedback_analysis_id ON analysis_feedback(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_feedback_contract_id ON analysis_feedback(contract_id);
CREATE INDEX IF NOT EXISTS idx_analysis_feedback_user_id ON analysis_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_feedback_rating ON analysis_feedback(overall_rating);

-- ===================================================
-- UPDATE TRIGGERS
-- ===================================================

-- Update timestamp trigger for contract_risks
CREATE OR REPLACE FUNCTION update_contract_risks_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_contract_risks_timestamp
    BEFORE UPDATE ON contract_risks
    FOR EACH ROW
    EXECUTE FUNCTION update_contract_risks_timestamp();

-- Update timestamp trigger for contract_recommendations
CREATE OR REPLACE FUNCTION update_contract_recommendations_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_contract_recommendations_timestamp
    BEFORE UPDATE ON contract_recommendations
    FOR EACH ROW
    EXECUTE FUNCTION update_contract_recommendations_timestamp();

-- Update timestamp trigger for contract_suggested_changes
CREATE OR REPLACE FUNCTION update_contract_suggested_changes_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_contract_suggested_changes_timestamp
    BEFORE UPDATE ON contract_suggested_changes
    FOR EACH ROW
    EXECUTE FUNCTION update_contract_suggested_changes_timestamp();

-- Update timestamp trigger for analysis_feedback
CREATE OR REPLACE FUNCTION update_analysis_feedback_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_analysis_feedback_timestamp
    BEFORE UPDATE ON analysis_feedback
    FOR EACH ROW
    EXECUTE FUNCTION update_analysis_feedback_timestamp();

-- ===================================================
-- COMMENTS
-- ===================================================

COMMENT ON TABLE contract_risks IS 'Identified risks in contract analysis';
COMMENT ON TABLE contract_recommendations IS 'Recommendations for contract improvement';
COMMENT ON TABLE contract_annotations IS 'Annotations for contract sections (separate JSON file approach)';
COMMENT ON TABLE contract_suggested_changes IS 'Suggested changes with automatic generation via LLM';
COMMENT ON TABLE analysis_feedback IS 'Feedback on analysis quality for ML training';

COMMENT ON COLUMN contract_risks.rag_sources IS 'JSON array of RAG sources (precedents, legal norms, analogues)';
COMMENT ON COLUMN contract_suggested_changes.status IS 'Approval status: pending/approved/rejected/modified';
COMMENT ON COLUMN analysis_feedback.missed_risks IS 'Array of risk descriptions that were missed by analysis';
COMMENT ON COLUMN analysis_feedback.false_positives IS 'Array of risks that were incorrectly identified';
