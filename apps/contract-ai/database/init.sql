-- =====================================================
-- Contract AI System - Database Schema
-- =====================================================
-- >445@6:0: PostgreSQL 14+ 8 SQLite 3.35+
-- =====================================================

--  0AH8@5=8O 4;O PostgreSQL
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- ;O 35=5@0F88 UUID
-- CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- ;O ?>;=>B5:AB>2>3> ?>8A:0

-- =====================================================
-- "01;8F0: users (?>;L7>20B5;8 A8AB5<K)
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'senior_lawyer', 'lawyer', 'junior_lawyer')),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =45:AK
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- =====================================================
-- "01;8F0: templates (H01;>=K 4>3>2>@>2)
-- =====================================================
CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    name VARCHAR(255) NOT NULL,
    contract_type VARCHAR(50) NOT NULL,  -- "supply", "service", "construction", etc.
    xml_content TEXT NOT NULL,
    structure TEXT,                      -- JSON: AB@C:BC@0 H01;>=0
    metadata TEXT,                       -- JSON: <5B040==K5 (required_fields, etc.)
    version VARCHAR(20) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(contract_type, version)
);

-- =45:AK
CREATE INDEX IF NOT EXISTS idx_templates_type ON templates(contract_type);
CREATE INDEX IF NOT EXISTS idx_templates_active ON templates(active);
CREATE INDEX IF NOT EXISTS idx_templates_created_by ON templates(created_by);

-- =====================================================
-- "01;8F0: contracts (4>3>2>@K)
-- =====================================================
CREATE TABLE IF NOT EXISTS contracts (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('contract', 'disagreement', 'tracked_changes')),
    contract_type VARCHAR(50),          -- "supply", "service", "construction", etc.
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'analyzing', 'reviewing', 'completed', 'error')),
    assigned_to TEXT REFERENCES users(id),
    risk_level VARCHAR(20) CHECK (risk_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    metadata TEXT,                      -- JSON: 4>?>;=8B5;L=K5 <5B040==K5
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =45:AK
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_risk_level ON contracts(risk_level);
CREATE INDEX IF NOT EXISTS idx_contracts_assigned_to ON contracts(assigned_to);
CREATE INDEX IF NOT EXISTS idx_contracts_document_type ON contracts(document_type);
CREATE INDEX IF NOT EXISTS idx_contracts_upload_date ON contracts(upload_date);

-- =====================================================
-- "01;8F0: analysis_results (@57C;LB0BK 0=0;870)
-- =====================================================
CREATE TABLE IF NOT EXISTS analysis_results (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    entities TEXT,                      -- JSON: 872;5G5==K5 ACI=>AB8
    compliance_issues TEXT,             -- JSON: =5A>>B25BAB28O AB0=40@B0<
    legal_issues TEXT,                  -- JSON: N@848G5A:85 @8A:8
    risks_by_category TEXT,             -- JSON: @8A:8 ?> :0B53>@8O<
    recommendations TEXT,               -- JSON: @5:><5=40F88
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

-- =45:AK
CREATE INDEX IF NOT EXISTS idx_analysis_contract_id ON analysis_results(contract_id);
CREATE INDEX IF NOT EXISTS idx_analysis_created_at ON analysis_results(created_at);

-- =====================================================
-- "01;8F0: review_tasks (7040G8 =0 ?@>25@:C)
-- =====================================================
CREATE TABLE IF NOT EXISTS review_tasks (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    assigned_to TEXT REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('critical', 'high', 'normal', 'low')),
    deadline TIMESTAMP,
    decision VARCHAR(50) CHECK (decision IN ('approve', 'reject', 'negotiate')),
    comments TEXT,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =45:AK
CREATE INDEX IF NOT EXISTS idx_review_tasks_assigned ON review_tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_review_tasks_status ON review_tasks(status);
CREATE INDEX IF NOT EXISTS idx_review_tasks_deadline ON review_tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_review_tasks_priority ON review_tasks(priority);

-- =====================================================
-- "01;8F0: legal_documents (1070 7=0=89 4;O RAG)
-- =====================================================
CREATE TABLE IF NOT EXISTS legal_documents (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    doc_id VARCHAR(64) UNIQUE NOT NULL,  -- Hash >B URL
    title TEXT NOT NULL,
    doc_type VARCHAR(50) NOT NULL,       -- "law", "code", "court_decision", etc.
    content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    is_vectorized BOOLEAN DEFAULT FALSE,
    metadata TEXT,                       -- JSON: 4>?>;=8B5;L=K5 <5B040==K5
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =45:AK
CREATE INDEX IF NOT EXISTS idx_legal_docs_type ON legal_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_legal_docs_status ON legal_documents(status);
CREATE INDEX IF NOT EXISTS idx_legal_docs_vectorized ON legal_documents(is_vectorized);

-- >;=>B5:AB>2K9 ?>8A: 4;O PostgreSQL (@0A:><<5=B8@C9 4;O PostgreSQL)
-- CREATE INDEX idx_legal_docs_content_fts ON legal_documents USING GIN(to_tsvector('russian', content));

-- ;O SQLite 8A?>;L7C5< ?@>AB>9 8=45:A
CREATE INDEX IF NOT EXISTS idx_legal_docs_doc_id ON legal_documents(doc_id);

-- =====================================================
-- "01;8F0: export_logs (;>38 M:A?>@B0)
-- =====================================================
CREATE TABLE IF NOT EXISTS export_logs (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    contract_id TEXT REFERENCES contracts(id) ON DELETE SET NULL,
    exported_by TEXT REFERENCES users(id),
    export_type VARCHAR(50),             -- "full_review", "quick_export"
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT                        -- JSON: 4>?>;=8B5;L=0O 8=D>@<0F8O
);

-- =45:AK
CREATE INDEX IF NOT EXISTS idx_export_logs_contract ON export_logs(contract_id);
CREATE INDEX IF NOT EXISTS idx_export_logs_user ON export_logs(exported_by);
CREATE INDEX IF NOT EXISTS idx_export_logs_date ON export_logs(exported_at);

-- =====================================================
-- "@8335@K 4;O 02B><0B8G5A:>3> >1=>2;5=8O updated_at
-- =====================================================

-- ;O SQLite
CREATE TRIGGER IF NOT EXISTS update_contracts_timestamp
AFTER UPDATE ON contracts
FOR EACH ROW
BEGIN
    UPDATE contracts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_templates_timestamp
AFTER UPDATE ON templates
FOR EACH ROW
BEGIN
    UPDATE templates SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_legal_docs_timestamp
AFTER UPDATE ON legal_documents
FOR EACH ROW
BEGIN
    UPDATE legal_documents SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- =====================================================
-- 0G0;L=K5 40==K5 (4;O B5AB8@>20=8O)
-- =====================================================

-- !>740=85 B5AB>2>3> ?>;L7>20B5;O
INSERT OR IGNORE INTO users (id, email, name, role) VALUES
('test-admin-001', 'admin@example.com', 'Admin User', 'admin'),
('test-lawyer-001', 'lawyer@example.com', 'Senior Lawyer', 'senior_lawyer');

-- =====================================================
-- =D>@<0F8O > AE5<5
-- =====================================================
-- 5@A8O AE5<K: 1.0
-- 0B0 A>740=8O: 2025-10-12
-- !>2<5AB8<>ABL: PostgreSQL 14+ 8 SQLite 3.35+
-- =====================================================
