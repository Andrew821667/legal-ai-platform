-- Performance Optimization: Database Indexes
-- Created during Phase 8: Performance Optimization
-- Adds composite indexes for frequently used query patterns

-- ============================================================================
-- CONTRACT RISKS - Composite indexes for common query patterns
-- ============================================================================

-- Index for filtering by contract + severity (common dashboard query)
CREATE INDEX IF NOT EXISTS idx_risks_contract_severity
ON contract_risks(contract_id, severity);

-- Index for filtering by contract + risk_type (risk analysis queries)
CREATE INDEX IF NOT EXISTS idx_risks_contract_type
ON contract_risks(contract_id, risk_type);

-- Index for time-based risk queries (trending analysis)
CREATE INDEX IF NOT EXISTS idx_risks_created_severity
ON contract_risks(created_at DESC, severity);

-- ============================================================================
-- CONTRACT RECOMMENDATIONS - Query optimization
-- ============================================================================

-- Index for filtering by contract + priority
CREATE INDEX IF NOT EXISTS idx_recommendations_contract_priority
ON contract_recommendations(contract_id, priority);

-- Index for category-based filtering
CREATE INDEX IF NOT EXISTS idx_recommendations_category_priority
ON contract_recommendations(category, priority);

-- ============================================================================
-- DISAGREEMENT MODELS - N+1 query optimization
-- ============================================================================

-- Index for fetching objections by disagreement (prevents N+1)
CREATE INDEX IF NOT EXISTS idx_objections_disagreement_created
ON disagreement_objections(disagreement_id, created_at DESC);

-- Index for feedback queries by objection
CREATE INDEX IF NOT EXISTS idx_feedback_objection_created
ON disagreement_feedback(objection_id, created_at DESC);

-- Index for effectiveness scoring queries
CREATE INDEX IF NOT EXISTS idx_disagreement_effectiveness
ON disagreements(effectiveness_score DESC)
WHERE effectiveness_score IS NOT NULL;

-- Composite index for filtering by date range + status
CREATE INDEX IF NOT EXISTS idx_disagreement_created_status
ON disagreements(created_at DESC, status);

-- ============================================================================
-- CONTRACTS - Common filtering patterns
-- ============================================================================

-- Index for status + upload date queries (contract dashboard)
CREATE INDEX IF NOT EXISTS idx_contracts_status_upload
ON contracts(status, upload_date DESC);

-- Index for assigned contracts (user workload queries)
CREATE INDEX IF NOT EXISTS idx_contracts_assigned_status
ON contracts(assigned_to, status)
WHERE assigned_to IS NOT NULL;

-- Index for risk level filtering
CREATE INDEX IF NOT EXISTS idx_contracts_risk_upload
ON contracts(risk_level, upload_date DESC)
WHERE risk_level IS NOT NULL;

-- ============================================================================
-- ANALYSIS RESULTS - Performance optimization
-- ============================================================================

-- Index for contract analysis history
CREATE INDEX IF NOT EXISTS idx_analysis_contract_created
ON analysis_results(contract_id, created_at DESC);

-- ============================================================================
-- REVIEW TASKS - Workload management
-- ============================================================================

-- Index for assigned tasks with status (reviewer dashboard)
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_status
ON review_tasks(assigned_to, status, due_date);

-- Index for overdue tasks
CREATE INDEX IF NOT EXISTS idx_tasks_due_status
ON review_tasks(due_date, status)
WHERE status != 'completed';

-- ============================================================================
-- EXPORT LOGS - Audit queries
-- ============================================================================

-- Index for user export history
CREATE INDEX IF NOT EXISTS idx_export_user_created
ON export_logs(user_id, created_at DESC);

-- Index for contract export history
CREATE INDEX IF NOT EXISTS idx_export_contract_format
ON export_logs(contract_id, export_format, created_at DESC);

-- ============================================================================
-- PARTIAL INDEXES (PostgreSQL-specific, improve specific query patterns)
-- ============================================================================

-- Index only active templates (most queries filter by active=true)
CREATE INDEX IF NOT EXISTS idx_templates_active_type
ON templates(contract_type, version)
WHERE active = true;

-- Index only active users
CREATE INDEX IF NOT EXISTS idx_users_active_role
ON users(role, email)
WHERE active = true;

-- Index only pending/in-progress contracts (completed contracts queried less)
CREATE INDEX IF NOT EXISTS idx_contracts_active
ON contracts(status, upload_date DESC, risk_level)
WHERE status IN ('pending', 'in_progress', 'review');

-- ============================================================================
-- STATISTICS UPDATE (PostgreSQL)
-- ============================================================================

-- Update statistics for query planner optimization
ANALYZE contract_risks;
ANALYZE contract_recommendations;
ANALYZE disagreements;
ANALYZE disagreement_objections;
ANALYZE disagreement_feedback;
ANALYZE contracts;
ANALYZE analysis_results;
ANALYZE review_tasks;
ANALYZE export_logs;

-- ============================================================================
-- INDEX MAINTENANCE NOTES
-- ============================================================================

/*
PERFORMANCE TIPS:

1. MONITORING:
   - Check index usage:
     SELECT * FROM pg_stat_user_indexes WHERE idx_scan = 0;
   - Remove unused indexes to save write performance

2. MAINTENANCE:
   - PostgreSQL: VACUUM ANALYZE regularly
   - SQLite: Run ANALYZE periodically
   - Consider REINDEX on heavily updated tables

3. QUERY OPTIMIZATION:
   - Use EXPLAIN ANALYZE to check if indexes are used
   - Monitor slow query log
   - Add indexes based on actual query patterns

4. WRITE PERFORMANCE:
   - Too many indexes slow down INSERT/UPDATE
   - Balance read vs write performance
   - Drop temporary indexes if not needed

5. COMPOSITE INDEX ORDERING:
   - Put high-cardinality columns first
   - Order matches most common queries
   - E.g., (contract_id, created_at) not (created_at, contract_id)

6. PARTIAL INDEXES:
   - Use WHERE clause for frequently filtered subsets
   - Smaller index = faster queries
   - PostgreSQL only (not supported in SQLite)
*/
