-- Migration: Add Enhanced Authentication Models
-- Date: 2025-01-15
-- Description: Adds User, DemoToken, UserSession, AuditLog and related tables

-- ==================== User Sessions ====================

CREATE TABLE IF NOT EXISTS user_sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    access_token VARCHAR(500) UNIQUE NOT NULL,
    refresh_token VARCHAR(500) UNIQUE NOT NULL,
    token_type VARCHAR(20) DEFAULT 'Bearer',
    ip_address VARCHAR(45),
    user_agent TEXT,
    device_info JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP,
    revoke_reason VARCHAR(255),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_session_user_active ON user_sessions(user_id, revoked, expires_at);
CREATE INDEX idx_session_access_token ON user_sessions(access_token);
CREATE INDEX idx_session_refresh_token ON user_sessions(refresh_token);
CREATE INDEX idx_session_created ON user_sessions(created_at);
CREATE INDEX idx_session_expires ON user_sessions(expires_at);

-- ==================== Demo Tokens ====================

CREATE TABLE IF NOT EXISTS demo_tokens (
    id VARCHAR(36) PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    max_contracts INTEGER DEFAULT 3,
    max_llm_requests INTEGER DEFAULT 10,
    max_file_size_mb INTEGER DEFAULT 5,
    expires_in_hours INTEGER DEFAULT 24,
    features JSON,
    used BOOLEAN DEFAULT FALSE,
    used_by_user_id VARCHAR(36),
    used_at TIMESTAMP,
    uses_count INTEGER DEFAULT 0,
    max_uses INTEGER DEFAULT 1,
    created_by VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    source VARCHAR(50),
    campaign VARCHAR(100),
    medium VARCHAR(50),
    referrer VARCHAR(255),
    notes TEXT,
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (used_by_user_id) REFERENCES users(id)
);

CREATE INDEX idx_demo_token_valid ON demo_tokens(token, used, expires_at);
CREATE INDEX idx_demo_token ON demo_tokens(token);
CREATE INDEX idx_demo_used ON demo_tokens(used);
CREATE INDEX idx_demo_expires ON demo_tokens(expires_at);
CREATE INDEX idx_demo_source_campaign ON demo_tokens(source, campaign);
CREATE INDEX idx_demo_created ON demo_tokens(created_at);

-- ==================== Audit Logs ====================

CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(36),
    status VARCHAR(20),
    error_message TEXT,
    details JSON,
    ip_address VARCHAR(45),
    user_agent TEXT,
    request_method VARCHAR(10),
    request_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER,
    severity VARCHAR(20),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_user_action ON audit_logs(user_id, action, created_at);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_severity_date ON audit_logs(severity, created_at);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
CREATE INDEX idx_audit_status ON audit_logs(status);
CREATE INDEX idx_audit_ip ON audit_logs(ip_address);

-- ==================== Password Reset Requests ====================

CREATE TABLE IF NOT EXISTS password_reset_requests (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_reset_token_valid ON password_reset_requests(token, used, expires_at);
CREATE INDEX idx_reset_user ON password_reset_requests(user_id);
CREATE INDEX idx_reset_expires ON password_reset_requests(expires_at);

-- ==================== Email Verifications ====================

CREATE TABLE IF NOT EXISTS email_verifications (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    email VARCHAR(255) NOT NULL,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resent_count INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_verification_token_valid ON email_verifications(token, verified, expires_at);
CREATE INDEX idx_verification_user ON email_verifications(user_id);
CREATE INDEX idx_verification_verified ON email_verifications(verified);

-- ==================== Login Attempts ====================

CREATE TABLE IF NOT EXISTS login_attempts (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    success BOOLEAN DEFAULT FALSE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    failure_reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_login_email_time ON login_attempts(email, created_at);
CREATE INDEX idx_login_ip_time ON login_attempts(ip_address, created_at);
CREATE INDEX idx_login_created ON login_attempts(created_at);
CREATE INDEX idx_login_success ON login_attempts(success);

-- ==================== Update Users Table ====================
-- Add new columns to existing users table (if they don't exist)

-- Check and add password_hash column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'password_hash'
    ) THEN
        ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);
    END IF;
END $$;

-- Add email verification columns
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'email_verified') THEN
        ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'verification_token') THEN
        ALTER TABLE users ADD COLUMN verification_token VARCHAR(255) UNIQUE;
    END IF;
END $$;

-- Add reset token columns
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'reset_token') THEN
        ALTER TABLE users ADD COLUMN reset_token VARCHAR(255) UNIQUE;
        ALTER TABLE users ADD COLUMN reset_token_expires TIMESTAMP;
    END IF;
END $$;

-- Add 2FA columns
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'two_factor_enabled') THEN
        ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT FALSE;
        ALTER TABLE users ADD COLUMN two_factor_secret VARCHAR(255);
        ALTER TABLE users ADD COLUMN backup_codes JSON;
    END IF;
END $$;

-- Add subscription columns
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'subscription_tier') THEN
        ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(50) DEFAULT 'demo';
        ALTER TABLE users ADD COLUMN subscription_expires TIMESTAMP;
        ALTER TABLE users ADD COLUMN subscription_auto_renew BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Add demo columns
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'is_demo') THEN
        ALTER TABLE users ADD COLUMN is_demo BOOLEAN DEFAULT FALSE;
        ALTER TABLE users ADD COLUMN demo_expires TIMESTAMP;
        ALTER TABLE users ADD COLUMN demo_token VARCHAR(255) UNIQUE;
    END IF;
END $$;

-- Add usage metrics
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'contracts_today') THEN
        ALTER TABLE users ADD COLUMN contracts_today INTEGER DEFAULT 0;
        ALTER TABLE users ADD COLUMN llm_requests_today INTEGER DEFAULT 0;
        ALTER TABLE users ADD COLUMN last_reset_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    END IF;
END $$;

-- Add audit columns
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'last_login') THEN
        ALTER TABLE users ADD COLUMN last_login TIMESTAMP;
        ALTER TABLE users ADD COLUMN last_ip VARCHAR(45);
        ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0;
    END IF;
END $$;

-- Add security columns
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'failed_login_attempts') THEN
        ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;
        ALTER TABLE users ADD COLUMN locked_until TIMESTAMP;
    END IF;
END $$;

-- Add preferences
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'preferences') THEN
        ALTER TABLE users ADD COLUMN preferences JSON;
        ALTER TABLE users ADD COLUMN notification_settings JSON;
    END IF;
END $$;

-- Create indexes for new user columns
CREATE INDEX IF NOT EXISTS idx_user_email_active ON users(email, active);
CREATE INDEX IF NOT EXISTS idx_user_demo_expires ON users(is_demo, demo_expires);
CREATE INDEX IF NOT EXISTS idx_user_subscription ON users(subscription_tier);
CREATE INDEX IF NOT EXISTS idx_user_last_login ON users(last_login);
CREATE INDEX IF NOT EXISTS idx_user_email_verified ON users(email_verified);
CREATE INDEX IF NOT EXISTS idx_user_verification_token ON users(verification_token);
CREATE INDEX IF NOT EXISTS idx_user_demo_token ON users(demo_token);

-- ==================== Analytics View ====================

-- Create view for user analytics
CREATE OR REPLACE VIEW user_analytics AS
SELECT
    DATE(created_at) as registration_date,
    role,
    subscription_tier,
    COUNT(*) as count,
    SUM(CASE WHEN is_demo THEN 1 ELSE 0 END) as demo_count,
    SUM(CASE WHEN email_verified THEN 1 ELSE 0 END) as verified_count,
    SUM(CASE WHEN active THEN 1 ELSE 0 END) as active_count
FROM users
GROUP BY DATE(created_at), role, subscription_tier;

-- Create view for login activity
CREATE OR REPLACE VIEW login_activity AS
SELECT
    DATE(created_at) as login_date,
    COUNT(*) as total_attempts,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_logins,
    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed_logins,
    COUNT(DISTINCT email) as unique_users,
    COUNT(DISTINCT ip_address) as unique_ips
FROM login_attempts
GROUP BY DATE(created_at);

-- ==================== Cleanup Old Sessions ====================

-- Create function to cleanup expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_sessions
    WHERE expires_at < CURRENT_TIMESTAMP AND revoked = FALSE;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ==================== Comments ====================

COMMENT ON TABLE user_sessions IS 'Active user sessions with JWT tokens';
COMMENT ON TABLE demo_tokens IS 'Tokens for demo access via links from website';
COMMENT ON TABLE audit_logs IS 'Audit trail for all user actions';
COMMENT ON TABLE password_reset_requests IS 'Password reset request tracking';
COMMENT ON TABLE email_verifications IS 'Email verification tracking';
COMMENT ON TABLE login_attempts IS 'Login attempt tracking for security';

-- ==================== Migration Complete ====================

-- Insert migration record (if migrations table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version') THEN
        INSERT INTO alembic_version (version_num) VALUES ('auth_models_2025_01_15')
        ON CONFLICT DO NOTHING;
    END IF;
END $$;
