-- Admin Database Schema for DB_CONNECTION_INFOS
-- This database stores user onboarding information

CREATE TABLE IF NOT EXISTS db_connection_infos (
    id SERIAL PRIMARY KEY,
    user_email TEXT UNIQUE NOT NULL,
    db_type TEXT NOT NULL DEFAULT 'postgres',
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 5432,
    db_user TEXT NOT NULL,
    db_password TEXT NOT NULL,  -- In production, encrypt this
    db_name TEXT NOT NULL,
    catalog_markdown TEXT,  -- Store the generated catalog
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_query_at TIMESTAMP,
    status TEXT DEFAULT 'active'
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_email ON db_connection_infos(user_email);
CREATE INDEX IF NOT EXISTS idx_status ON db_connection_infos(status);

-- Audit log for tracking
CREATE TABLE IF NOT EXISTS onboarding_audit_log (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    action TEXT,  -- 'onboard', 'catalog_update', 'query', etc.
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_email ON onboarding_audit_log(user_email);

