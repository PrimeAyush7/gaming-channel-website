-- Migration 002: Extend Admin Roles & Audit Logging
ALTER TABLE admins ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'SUPER_ADMIN';
ALTER TABLE admins ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE admins ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1;
ALTER TABLE admins ADD COLUMN IF NOT EXISTS must_change_password INTEGER DEFAULT 0;

CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    admin_username VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    resource_id VARCHAR(100),
    ip_address VARCHAR(100) NOT NULL,
    user_agent TEXT,
    before_state TEXT,
    after_state TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_admin_id ON admin_audit_logs(admin_id);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON admin_audit_logs(resource, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON admin_audit_logs(created_at);
