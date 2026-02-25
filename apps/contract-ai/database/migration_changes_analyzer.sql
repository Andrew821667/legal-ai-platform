-- Migration: Changes Analyzer Tables
-- Description: Contract versioning and change tracking system
-- Author: AI Assistant
-- Date: 2025-01-13

-- =====================================================
-- Table 1: contract_versions
-- Stores all versions of a contract with metadata
-- =====================================================
CREATE TABLE IF NOT EXISTS contract_versions (
    id SERIAL PRIMARY KEY,
    contract_id VARCHAR(36) NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64), -- SHA256 hash for integrity
    uploaded_by VARCHAR(36) REFERENCES users(id),
    uploaded_at TIMESTAMP DEFAULT NOW(),
    source VARCHAR(50) DEFAULT 'unknown', -- 'initial', 'counterparty_response', 'internal_revision'
    description TEXT,
    parent_version_id INTEGER REFERENCES contract_versions(id),
    is_current BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT uq_contract_version UNIQUE(contract_id, version_number),
    CONSTRAINT check_version_number CHECK (version_number > 0),
    CONSTRAINT check_source CHECK (source IN ('initial', 'counterparty_response', 'internal_revision', 'final', 'unknown'))
);

CREATE INDEX idx_contract_versions_contract_id ON contract_versions(contract_id);
CREATE INDEX idx_contract_versions_uploaded_at ON contract_versions(uploaded_at);
CREATE INDEX idx_contract_versions_is_current ON contract_versions(is_current);
CREATE INDEX idx_contract_versions_source ON contract_versions(source);

-- =====================================================
-- Table 2: contract_changes
-- Detailed records of individual changes between versions
-- =====================================================
CREATE TABLE IF NOT EXISTS contract_changes (
    id SERIAL PRIMARY KEY,
    from_version_id INTEGER NOT NULL REFERENCES contract_versions(id) ON DELETE CASCADE,
    to_version_id INTEGER NOT NULL REFERENCES contract_versions(id) ON DELETE CASCADE,

    -- Change classification
    change_type VARCHAR(50) NOT NULL, -- 'addition', 'deletion', 'modification', 'relocation'
    change_category VARCHAR(50) NOT NULL, -- 'textual', 'structural', 'semantic', 'legal'

    -- Location in document
    xpath_location TEXT,
    section_name VARCHAR(255),
    clause_number VARCHAR(50),

    -- Content
    old_content TEXT,
    new_content TEXT,

    -- Semantic analysis (from LLM)
    semantic_description TEXT,
    is_substantive BOOLEAN DEFAULT TRUE,
    legal_implications TEXT,

    -- Impact assessment
    impact_assessment JSONB DEFAULT '{}',
    -- {
    --   "direction": "positive/negative/neutral",
    --   "severity": "critical/significant/minor",
    --   "affected_risks": [{"risk_id": 1, "impact": "increases"}],
    --   "new_risks": [{"description": "...", "severity": "..."}],
    --   "recommendation": "accept/reject/negotiate",
    --   "reasoning": "..."
    -- }

    -- Link to disagreements
    related_disagreement_objection_id INTEGER REFERENCES disagreement_objections(id),
    objection_status VARCHAR(20), -- 'accepted', 'rejected', 'partial', 'unrelated'

    -- Review workflow
    requires_lawyer_review BOOLEAN DEFAULT FALSE,
    reviewed_by VARCHAR(36) REFERENCES users(id),
    reviewed_at TIMESTAMP,
    lawyer_decision VARCHAR(20), -- 'approve', 'reject', 'negotiate'
    lawyer_comments TEXT,

    -- Metadata
    detected_by VARCHAR(50) DEFAULT 'ChangesAnalyzerAgent',
    confidence_score FLOAT, -- 0.0-1.0 for ML
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_change_type CHECK (change_type IN ('addition', 'deletion', 'modification', 'relocation')),
    CONSTRAINT check_change_category CHECK (change_category IN ('textual', 'structural', 'semantic', 'legal')),
    CONSTRAINT check_objection_status CHECK (objection_status IN ('accepted', 'rejected', 'partial', 'unrelated', NULL)),
    CONSTRAINT check_lawyer_decision CHECK (lawyer_decision IN ('approve', 'reject', 'negotiate', NULL)),
    CONSTRAINT check_confidence_score CHECK (confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0))
);

CREATE INDEX idx_contract_changes_from_version ON contract_changes(from_version_id);
CREATE INDEX idx_contract_changes_to_version ON contract_changes(to_version_id);
CREATE INDEX idx_contract_changes_type ON contract_changes(change_type);
CREATE INDEX idx_contract_changes_category ON contract_changes(change_category);
CREATE INDEX idx_contract_changes_objection ON contract_changes(related_disagreement_objection_id);
CREATE INDEX idx_contract_changes_requires_review ON contract_changes(requires_lawyer_review);
CREATE INDEX idx_contract_changes_created_at ON contract_changes(created_at);

-- =====================================================
-- Table 3: change_analysis_results
-- Summary analysis of changes between two versions
-- =====================================================
CREATE TABLE IF NOT EXISTS change_analysis_results (
    id SERIAL PRIMARY KEY,
    from_version_id INTEGER NOT NULL REFERENCES contract_versions(id) ON DELETE CASCADE,
    to_version_id INTEGER NOT NULL REFERENCES contract_versions(id) ON DELETE CASCADE,

    -- Statistics
    total_changes INTEGER DEFAULT 0,
    by_type JSONB DEFAULT '{}', -- {"addition": 5, "deletion": 2, "modification": 10, "relocation": 1}
    by_category JSONB DEFAULT '{}', -- {"textual": 8, "structural": 3, "semantic": 4, "legal": 3}
    by_impact JSONB DEFAULT '{}', -- {"positive": 3, "negative": 5, "neutral": 10}

    -- Overall assessment
    overall_assessment VARCHAR(20), -- 'favorable', 'unfavorable', 'mixed', 'neutral'
    overall_risk_change VARCHAR(20), -- 'increased', 'decreased', 'unchanged'

    -- Critical changes (list of change IDs)
    critical_changes JSONB DEFAULT '[]',

    -- Disagreement tracking
    accepted_objections INTEGER DEFAULT 0,
    rejected_objections INTEGER DEFAULT 0,
    partial_objections INTEGER DEFAULT 0,

    -- LLM recommendations
    recommendations TEXT,
    executive_summary TEXT, -- Brief summary for management

    -- Report generation
    report_pdf_path TEXT,
    report_generated_at TIMESTAMP,

    -- Metadata
    analyzed_at TIMESTAMP DEFAULT NOW(),
    analyzed_by VARCHAR(50) DEFAULT 'ChangesAnalyzerAgent',
    analysis_duration_ms INTEGER, -- performance tracking

    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT uq_change_analysis UNIQUE(from_version_id, to_version_id),
    CONSTRAINT check_overall_assessment CHECK (overall_assessment IN ('favorable', 'unfavorable', 'mixed', 'neutral', NULL)),
    CONSTRAINT check_overall_risk_change CHECK (overall_risk_change IN ('increased', 'decreased', 'unchanged', NULL))
);

CREATE INDEX idx_change_analysis_from_version ON change_analysis_results(from_version_id);
CREATE INDEX idx_change_analysis_to_version ON change_analysis_results(to_version_id);
CREATE INDEX idx_change_analysis_overall_assessment ON change_analysis_results(overall_assessment);
CREATE INDEX idx_change_analysis_analyzed_at ON change_analysis_results(analyzed_at);

-- =====================================================
-- Table 4: change_review_feedback
-- Feedback from lawyers on change decisions (for ML training)
-- =====================================================
CREATE TABLE IF NOT EXISTS change_review_feedback (
    id SERIAL PRIMARY KEY,
    change_id INTEGER NOT NULL REFERENCES contract_changes(id) ON DELETE CASCADE,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),

    -- Decision
    decision VARCHAR(20) NOT NULL, -- 'approve', 'reject', 'negotiate'
    reasoning TEXT,

    -- Quality ratings (1-5)
    analysis_accuracy INTEGER, -- How accurate was the change detection?
    impact_assessment_quality INTEGER, -- How accurate was the impact assessment?
    recommendation_usefulness INTEGER, -- Was the recommendation helpful?

    -- Outcome
    what_happened VARCHAR(20), -- 'accepted_by_counterparty', 'rejected_by_counterparty', 'negotiated', 'pending'
    outcome_notes TEXT,

    -- ML training data
    was_correct_recommendation BOOLEAN,

    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_decision CHECK (decision IN ('approve', 'reject', 'negotiate')),
    CONSTRAINT check_analysis_accuracy CHECK (analysis_accuracy IS NULL OR (analysis_accuracy >= 1 AND analysis_accuracy <= 5)),
    CONSTRAINT check_impact_quality CHECK (impact_assessment_quality IS NULL OR (impact_assessment_quality >= 1 AND impact_assessment_quality <= 5)),
    CONSTRAINT check_recommendation_usefulness CHECK (recommendation_usefulness IS NULL OR (recommendation_usefulness >= 1 AND recommendation_usefulness <= 5)),
    CONSTRAINT check_what_happened CHECK (what_happened IN ('accepted_by_counterparty', 'rejected_by_counterparty', 'negotiated', 'pending', NULL))
);

CREATE INDEX idx_change_review_feedback_change_id ON change_review_feedback(change_id);
CREATE INDEX idx_change_review_feedback_user_id ON change_review_feedback(user_id);
CREATE INDEX idx_change_review_feedback_decision ON change_review_feedback(decision);
CREATE INDEX idx_change_review_feedback_created_at ON change_review_feedback(created_at);

-- =====================================================
-- Trigger: Update contract_versions.updated_at
-- =====================================================
CREATE OR REPLACE FUNCTION update_contract_versions_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_contract_versions_timestamp
BEFORE UPDATE ON contract_versions
FOR EACH ROW
EXECUTE FUNCTION update_contract_versions_timestamp();

-- =====================================================
-- Trigger: Ensure only one current version per contract
-- =====================================================
CREATE OR REPLACE FUNCTION ensure_single_current_version()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current = TRUE THEN
        UPDATE contract_versions
        SET is_current = FALSE
        WHERE contract_id = NEW.contract_id
          AND id != NEW.id
          AND is_current = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_ensure_single_current_version
AFTER INSERT OR UPDATE ON contract_versions
FOR EACH ROW
WHEN (NEW.is_current = TRUE)
EXECUTE FUNCTION ensure_single_current_version();

-- =====================================================
-- Comments
-- =====================================================
COMMENT ON TABLE contract_versions IS 'Хранение всех версий договоров с метаданными';
COMMENT ON TABLE contract_changes IS 'Детальная информация об изменениях между версиями';
COMMENT ON TABLE change_analysis_results IS 'Сводный анализ изменений между версиями';
COMMENT ON TABLE change_review_feedback IS 'Обратная связь от юристов для обучения ML';

COMMENT ON COLUMN contract_changes.impact_assessment IS 'JSON с оценкой влияния изменения на риски и позицию компании';
COMMENT ON COLUMN contract_changes.confidence_score IS 'Уверенность модели в классификации (для ML)';
COMMENT ON COLUMN change_analysis_results.critical_changes IS 'Список ID критических изменений, требующих немедленного внимания';
COMMENT ON COLUMN change_review_feedback.was_correct_recommendation IS 'Была ли рекомендация агента правильной (ground truth для обучения)';
