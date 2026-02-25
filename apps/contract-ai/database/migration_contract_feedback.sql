-- Contract Feedback Table for ML Training Data Collection
-- Stores user feedback on generated contracts for future fine-tuning

CREATE TABLE IF NOT EXISTS contract_feedback (
    id SERIAL PRIMARY KEY,
    contract_id INTEGER REFERENCES contracts(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- User feedback
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    acceptance_status BOOLEAN DEFAULT NULL,  -- true=accepted, false=rejected, null=pending

    -- User corrections (what user changed)
    user_corrections JSONB DEFAULT '{}',

    -- Generation parameters (for reproducing)
    generation_params JSONB DEFAULT '{}',

    -- Template and context used
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    rag_context_used JSONB DEFAULT '{}',

    -- Quality metrics
    validation_errors INTEGER DEFAULT 0,
    validation_warnings INTEGER DEFAULT 0,
    generation_duration FLOAT,

    -- Comments
    user_comment TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_contract_feedback_contract_id ON contract_feedback(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_feedback_user_id ON contract_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_contract_feedback_rating ON contract_feedback(rating);
CREATE INDEX IF NOT EXISTS idx_contract_feedback_acceptance ON contract_feedback(acceptance_status);
CREATE INDEX IF NOT EXISTS idx_contract_feedback_created_at ON contract_feedback(created_at DESC);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_contract_feedback_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_contract_feedback_timestamp
    BEFORE UPDATE ON contract_feedback
    FOR EACH ROW
    EXECUTE FUNCTION update_contract_feedback_timestamp();

COMMENT ON TABLE contract_feedback IS 'User feedback on generated contracts for ML training data collection';
COMMENT ON COLUMN contract_feedback.rating IS 'User rating 1-5 stars';
COMMENT ON COLUMN contract_feedback.acceptance_status IS 'Whether user accepted (true), rejected (false), or pending (null)';
COMMENT ON COLUMN contract_feedback.user_corrections IS 'JSON with user modifications to generated contract';
COMMENT ON COLUMN contract_feedback.generation_params IS 'Parameters used for contract generation';
COMMENT ON COLUMN contract_feedback.rag_context_used IS 'RAG context that was used during generation';
