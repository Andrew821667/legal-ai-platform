-- Disagreement Tables
-- Tables for storing disagreements/objections to external contracts

-- ===================================================
-- 1. DISAGREEMENTS (основной документ возражений)
-- ===================================================
CREATE TABLE IF NOT EXISTS disagreements (
    id SERIAL PRIMARY KEY,
    contract_id INTEGER REFERENCES contracts(id) ON DELETE CASCADE,
    analysis_id INTEGER REFERENCES analysis_results(id) ON DELETE CASCADE,
    
    -- Workflow status
    status VARCHAR(20) DEFAULT 'draft',  -- draft, review, approved, sent, responded
    
    -- Content
    generated_content JSONB DEFAULT '{}',  -- все сгенерированные возражения
    selected_objections JSONB DEFAULT '[]',  -- ID выбранных юристом возражений
    priority_order JSONB DEFAULT '[]',  -- порядок важности [id1, id2, ...]
    
    -- Export formats
    xml_content TEXT,  -- структурированный XML
    docx_path VARCHAR(500),  -- путь к DOCX файлу
    pdf_path VARCHAR(500),  -- путь к PDF файлу
    
    -- Response tracking
    response_status VARCHAR(20),  -- pending, accepted, rejected, partial
    response_notes TEXT,  -- заметки по ответу контрагента
    effectiveness_score FLOAT,  -- 0.0-1.0 для ML обучения
    
    -- Metadata
    tone VARCHAR(20) DEFAULT 'neutral_business',  -- нейтрально-деловой
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    responded_at TIMESTAMP,
    
    CONSTRAINT check_disagreement_status CHECK (status IN ('draft', 'review', 'approved', 'sent', 'responded')),
    CONSTRAINT check_response_status CHECK (response_status IN ('pending', 'accepted', 'rejected', 'partial', NULL)),
    CONSTRAINT check_effectiveness_score CHECK (effectiveness_score >= 0.0 AND effectiveness_score <= 1.0 OR effectiveness_score IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_disagreements_contract_id ON disagreements(contract_id);
CREATE INDEX IF NOT EXISTS idx_disagreements_analysis_id ON disagreements(analysis_id);
CREATE INDEX IF NOT EXISTS idx_disagreements_status ON disagreements(status);
CREATE INDEX IF NOT EXISTS idx_disagreements_response_status ON disagreements(response_status);

-- ===================================================
-- 2. DISAGREEMENT OBJECTIONS (отдельные возражения)
-- ===================================================
CREATE TABLE IF NOT EXISTS disagreement_objections (
    id SERIAL PRIMARY KEY,
    disagreement_id INTEGER REFERENCES disagreements(id) ON DELETE CASCADE,
    
    -- Связь с рисками и договором
    related_risk_ids JSONB DEFAULT '[]',  -- [risk_id1, risk_id2, ...]
    contract_section_xpath TEXT,  -- XPath к пункту договора
    contract_section_text TEXT,  -- текст проблемного пункта
    
    -- Структура возражения
    issue_description TEXT NOT NULL,  -- описание проблемы
    legal_basis TEXT,  -- правовое обоснование (ссылки на законы)
    precedents JSONB DEFAULT '[]',  -- прецеденты из RAG
    risk_explanation TEXT,  -- объяснение рисков
    
    -- Альтернативные формулировки
    alternative_formulation TEXT,  -- предлагаемая формулировка
    alternative_reasoning TEXT,  -- обоснование альтернативы
    alternative_variants JSONB DEFAULT '[]',  -- дополнительные варианты
    
    -- Приоритизация
    priority VARCHAR(20) DEFAULT 'medium',  -- critical, high, medium, low
    auto_priority INTEGER,  -- автоматический приоритет (1-100)
    user_priority INTEGER,  -- приоритет от юриста (1-100)
    
    -- Выбор юристом
    user_selected BOOLEAN DEFAULT FALSE,
    user_modified BOOLEAN DEFAULT FALSE,
    original_content TEXT,  -- оригинальная версия LLM
    
    -- Response tracking
    counterparty_response VARCHAR(20),  -- accepted, rejected, negotiated, null
    effectiveness_feedback TEXT,  -- обратная связь по эффективности
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT check_objection_priority CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    CONSTRAINT check_counterparty_response CHECK (counterparty_response IN ('accepted', 'rejected', 'negotiated', NULL))
);

CREATE INDEX IF NOT EXISTS idx_disagreement_objections_disagreement_id ON disagreement_objections(disagreement_id);
CREATE INDEX IF NOT EXISTS idx_disagreement_objections_priority ON disagreement_objections(priority);
CREATE INDEX IF NOT EXISTS idx_disagreement_objections_user_selected ON disagreement_objections(user_selected);
CREATE INDEX IF NOT EXISTS idx_disagreement_objections_response ON disagreement_objections(counterparty_response);

-- ===================================================
-- 3. DISAGREEMENT EXPORT LOG (логи отправки)
-- ===================================================
CREATE TABLE IF NOT EXISTS disagreement_export_log (
    id SERIAL PRIMARY KEY,
    disagreement_id INTEGER REFERENCES disagreements(id) ON DELETE CASCADE,
    
    -- Export details
    export_type VARCHAR(50) NOT NULL,  -- docx, pdf, email, edo
    export_format VARCHAR(20),  -- для edo: diadoc, sbis, etc
    
    -- File paths
    file_path VARCHAR(500),
    file_size INTEGER,
    file_hash VARCHAR(64),  -- SHA256
    
    -- Email details (if applicable)
    email_to VARCHAR(255),
    email_subject VARCHAR(500),
    email_sent_at TIMESTAMP,
    email_status VARCHAR(20),  -- sent, failed, pending
    
    -- EDO details (if applicable)
    edo_system VARCHAR(50),
    edo_document_id VARCHAR(255),
    edo_status VARCHAR(50),
    
    -- Metadata
    exported_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    export_metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT check_export_type CHECK (export_type IN ('docx', 'pdf', 'email', 'edo', 'api'))
);

CREATE INDEX IF NOT EXISTS idx_disagreement_export_log_disagreement_id ON disagreement_export_log(disagreement_id);
CREATE INDEX IF NOT EXISTS idx_disagreement_export_log_export_type ON disagreement_export_log(export_type);

-- ===================================================
-- 4. DISAGREEMENT FEEDBACK (обратная связь для ML)
-- ===================================================
CREATE TABLE IF NOT EXISTS disagreement_feedback (
    id SERIAL PRIMARY KEY,
    disagreement_id INTEGER REFERENCES disagreements(id) ON DELETE CASCADE,
    objection_id INTEGER REFERENCES disagreement_objections(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Overall feedback
    overall_quality INTEGER CHECK (overall_quality >= 1 AND overall_quality <= 5),
    usefulness_rating INTEGER CHECK (usefulness_rating >= 1 AND usefulness_rating <= 5),
    
    -- Specific feedback
    tone_appropriateness INTEGER CHECK (tone_appropriateness >= 1 AND tone_appropriateness <= 5),
    legal_basis_quality INTEGER CHECK (legal_basis_quality >= 1 AND legal_basis_quality <= 5),
    alternative_quality INTEGER CHECK (alternative_quality >= 1 AND alternative_quality <= 5),
    
    -- Outcome
    was_accepted BOOLEAN,
    was_negotiated BOOLEAN,
    led_to_contract_change BOOLEAN,
    
    -- Comments
    what_worked_well TEXT,
    what_needs_improvement TEXT,
    suggestions TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_disagreement_feedback_disagreement_id ON disagreement_feedback(disagreement_id);
CREATE INDEX IF NOT EXISTS idx_disagreement_feedback_objection_id ON disagreement_feedback(objection_id);
CREATE INDEX IF NOT EXISTS idx_disagreement_feedback_user_id ON disagreement_feedback(user_id);

-- ===================================================
-- UPDATE TRIGGERS
-- ===================================================

-- Update timestamp trigger for disagreements
CREATE OR REPLACE FUNCTION update_disagreements_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_disagreements_timestamp
    BEFORE UPDATE ON disagreements
    FOR EACH ROW
    EXECUTE FUNCTION update_disagreements_timestamp();

-- Update timestamp trigger for disagreement_objections
CREATE OR REPLACE FUNCTION update_disagreement_objections_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_disagreement_objections_timestamp
    BEFORE UPDATE ON disagreement_objections
    FOR EACH ROW
    EXECUTE FUNCTION update_disagreement_objections_timestamp();

-- Update timestamp trigger for disagreement_feedback
CREATE OR REPLACE FUNCTION update_disagreement_feedback_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_disagreement_feedback_timestamp
    BEFORE UPDATE ON disagreement_feedback
    FOR EACH ROW
    EXECUTE FUNCTION update_disagreement_feedback_timestamp();

-- ===================================================
-- COMMENTS
-- ===================================================

COMMENT ON TABLE disagreements IS 'Main disagreement documents with workflow and tracking';
COMMENT ON TABLE disagreement_objections IS 'Individual objections with legal basis and alternatives';
COMMENT ON TABLE disagreement_export_log IS 'Export and delivery tracking (DOCX, PDF, Email, EDO)';
COMMENT ON TABLE disagreement_feedback IS 'Feedback on disagreement quality for ML training';

COMMENT ON COLUMN disagreements.generated_content IS 'All LLM-generated objections (JSON)';
COMMENT ON COLUMN disagreements.selected_objections IS 'Array of objection IDs selected by lawyer';
COMMENT ON COLUMN disagreements.priority_order IS 'Order of importance [id1, id2, ...]';
COMMENT ON COLUMN disagreements.effectiveness_score IS 'ML training score: 0.0 (failed) to 1.0 (fully accepted)';

COMMENT ON COLUMN disagreement_objections.related_risk_ids IS 'Array of contract_risks.id that this objection addresses';
COMMENT ON COLUMN disagreement_objections.precedents IS 'RAG sources: similar objections, court decisions, etc';
COMMENT ON COLUMN disagreement_objections.alternative_variants IS 'Array of alternative formulations with reasoning';
COMMENT ON COLUMN disagreement_objections.user_selected IS 'Whether lawyer selected this objection for final document';
COMMENT ON COLUMN disagreement_objections.counterparty_response IS 'How counterparty responded: accepted/rejected/negotiated';
