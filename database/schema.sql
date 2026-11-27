-- ==============================================================================
-- NovaEnterprise Relational Schema DDL (PostgreSQL)
-- ==============================================================================
-- Generated from SQLAlchemy declarative models for all 16 platform entities.
-- ==============================================================================

-- 1. Teams
CREATE TABLE IF NOT EXISTS teams (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    lead VARCHAR(128),
    slack_channel VARCHAR(64),
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Employees
CREATE TABLE IF NOT EXISTS employees (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    email VARCHAR(128) NOT NULL UNIQUE,
    role VARCHAR(64),
    team_id VARCHAR(64) NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Services
CREATE TABLE IF NOT EXISTS services (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    tier VARCHAR(32) NOT NULL DEFAULT 'tier-2',
    port INTEGER,
    repo_url VARCHAR(256),
    owner_team_id VARCHAR(64) REFERENCES teams(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Customers
CREATE TABLE IF NOT EXISTS customers (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    tier VARCHAR(32) NOT NULL DEFAULT 'standard',
    contract_value NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    industry VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Incidents
CREATE TABLE IF NOT EXISTS incidents (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'investigating',
    root_cause TEXT,
    impacted_service_id VARCHAR(64) REFERENCES services(id) ON DELETE SET NULL,
    occurred_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Decisions (ADRs)
CREATE TABLE IF NOT EXISTS decisions (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'proposed',
    context TEXT,
    decision TEXT,
    consequences TEXT,
    incident_id VARCHAR(64) REFERENCES incidents(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Projects
CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    owner_team_id VARCHAR(64) REFERENCES teams(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Tickets
CREATE TABLE IF NOT EXISTS tickets (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    priority VARCHAR(16) NOT NULL DEFAULT 'P2',
    project_id VARCHAR(64) REFERENCES projects(id) ON DELETE CASCADE,
    assignee_id VARCHAR(64) REFERENCES employees(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Research Sessions
CREATE TABLE IF NOT EXISTS research_sessions (
    id VARCHAR(36) PRIMARY KEY,
    question TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    complexity VARCHAR(32),
    answer TEXT,
    sub_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_data JSONB NOT NULL DEFAULT '[]'::jsonb,
    execution_time FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Workflow Events
CREATE TABLE IF NOT EXISTS workflow_events (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
    node_name VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL DEFAULT 'node_complete',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    latency_ms INTEGER,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_workflow_events_session_id ON workflow_events(session_id);

-- 11. Citation Records
CREATE TABLE IF NOT EXISTS citation_records (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
    chunk_id VARCHAR(64),
    document_id VARCHAR(64),
    locator VARCHAR(128),
    text_snippet TEXT,
    score FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_citation_records_session_id ON citation_records(session_id);

-- 12. Documents
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(256) NOT NULL,
    content_hash VARCHAR(64) NOT NULL UNIQUE,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    flagged_injection BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_documents_content_hash ON documents(content_hash);

-- 13. Document Chunks
CREATE TABLE IF NOT EXISTS document_chunks (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding_id VARCHAR(64),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id ON document_chunks(document_id);

-- 14. Approval Requests
CREATE TABLE IF NOT EXISTS approval_requests (
    id VARCHAR(36) PRIMARY KEY,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(64) NOT NULL,
    action VARCHAR(32) NOT NULL DEFAULT 'delete',
    requester_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    decided_by VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_approval_requests_resource_id ON approval_requests(resource_id);

-- 15. Users
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(128) NOT NULL UNIQUE,
    role VARCHAR(32) NOT NULL DEFAULT 'analyst',
    hashed_password VARCHAR(256) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);

-- 16. Audit Logs (Append-Only)
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64),
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64),
    resource_id VARCHAR(64),
    request_id VARCHAR(64),
    ip_address VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_request_id ON audit_logs(request_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id);
