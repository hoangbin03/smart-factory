-- Factory Platform - PostgreSQL Initialization Script
-- Creates all databases and schemas for all services

-- ─────────────────────────────────────────
-- EXTENSIONS
-- ─────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ─────────────────────────────────────────
-- ENUMS
-- ─────────────────────────────────────────
DO $$ BEGIN
  CREATE TYPE workflow_status AS ENUM (
    'PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE task_status AS ENUM (
    'PENDING', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED', 'CANCELLED'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE agent_status AS ENUM (
    'HEALTHY', 'DEGRADED', 'OFFLINE', 'MAINTENANCE'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE approval_status AS ENUM (
    'PENDING', 'APPROVED', 'REJECTED', 'ESCALATED', 'EXPIRED'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE audit_action AS ENUM (
    'CREATE', 'UPDATE', 'DELETE', 'EXECUTE', 'APPROVE', 'REJECT', 'LOGIN', 'LOGOUT'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ─────────────────────────────────────────
-- WORKFLOW SERVICE TABLES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workflows (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name          VARCHAR(255) NOT NULL,
  description   TEXT,
  status        workflow_status NOT NULL DEFAULT 'PENDING',
  goal          TEXT NOT NULL,
  config        JSONB DEFAULT '{}',
  metadata      JSONB DEFAULT '{}',
  created_by    UUID,
  started_at    TIMESTAMPTZ,
  completed_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
CREATE INDEX IF NOT EXISTS idx_workflows_created_at ON workflows(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflows_metadata ON workflows USING GIN(metadata);

-- ─────────────────────────────────────────
-- TASK SERVICE TABLES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  workflow_id   UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  name          VARCHAR(255) NOT NULL,
  description   TEXT,
  status        task_status NOT NULL DEFAULT 'PENDING',
  agent_id      VARCHAR(100),
  goal          TEXT NOT NULL,
  input         JSONB DEFAULT '{}',
  output        JSONB DEFAULT '{}',
  constraints   JSONB DEFAULT '{}',
  "order"       INTEGER NOT NULL DEFAULT 0,
  retry_count   INTEGER NOT NULL DEFAULT 0,
  max_retries   INTEGER NOT NULL DEFAULT 3,
  started_at    TIMESTAMPTZ,
  completed_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_workflow_id ON tasks(workflow_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_agent_id ON tasks(agent_id);

-- ─────────────────────────────────────────
-- AGENT REGISTRY TABLES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_id      VARCHAR(100) UNIQUE NOT NULL,
  name          VARCHAR(255) NOT NULL,
  description   TEXT,
  role          VARCHAR(100) NOT NULL,
  runtime       VARCHAR(50) NOT NULL DEFAULT 'nemo',
  capabilities  TEXT[] DEFAULT ARRAY[]::TEXT[],
  tools         TEXT[] DEFAULT ARRAY[]::TEXT[],
  status        agent_status NOT NULL DEFAULT 'HEALTHY',
  config        JSONB DEFAULT '{}',
  version       VARCHAR(20) NOT NULL DEFAULT '1.0.0',
  last_seen_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_role ON agents(role);

-- ─────────────────────────────────────────
-- APPROVAL SERVICE TABLES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS approvals (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  workflow_id   UUID REFERENCES workflows(id) ON DELETE CASCADE,
  task_id       UUID REFERENCES tasks(id) ON DELETE CASCADE,
  title         VARCHAR(255) NOT NULL,
  description   TEXT,
  status        approval_status NOT NULL DEFAULT 'PENDING',
  requested_by  UUID,
  approved_by   UUID,
  decision_at   TIMESTAMPTZ,
  expires_at    TIMESTAMPTZ,
  notes         TEXT,
  metadata      JSONB DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approvals_workflow_id ON approvals(workflow_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);

-- ─────────────────────────────────────────
-- AUDIT SERVICE TABLES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  action        audit_action NOT NULL,
  entity_type   VARCHAR(100) NOT NULL,
  entity_id     UUID,
  actor_id      UUID,
  actor_type    VARCHAR(50) DEFAULT 'user',
  changes       JSONB DEFAULT '{}',
  metadata      JSONB DEFAULT '{}',
  ip_address    INET,
  user_agent    TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_id);

-- ─────────────────────────────────────────
-- AGENT MEMORY TABLES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_memories (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_id      VARCHAR(100) NOT NULL,
  workflow_id   UUID REFERENCES workflows(id) ON DELETE SET NULL,
  memory_type   VARCHAR(50) NOT NULL DEFAULT 'episodic',
  key           VARCHAR(255) NOT NULL,
  value         JSONB NOT NULL,
  tags          TEXT[] DEFAULT ARRAY[]::TEXT[],
  expires_at    TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_memories_agent_id ON agent_memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_memories_key ON agent_memories(agent_id, key);
CREATE INDEX IF NOT EXISTS idx_agent_memories_tags ON agent_memories USING GIN(tags);

CREATE TABLE IF NOT EXISTS agent_sessions (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_id      VARCHAR(100) NOT NULL,
  workflow_id   UUID REFERENCES workflows(id) ON DELETE CASCADE,
  task_id       UUID REFERENCES tasks(id) ON DELETE CASCADE,
  session_data  JSONB NOT NULL DEFAULT '{}',
  started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at      TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_agent_id ON agent_sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_workflow_id ON agent_sessions(workflow_id);

CREATE TABLE IF NOT EXISTS agent_artifacts (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_id      VARCHAR(100) NOT NULL,
  workflow_id   UUID REFERENCES workflows(id) ON DELETE CASCADE,
  task_id       UUID REFERENCES tasks(id) ON DELETE CASCADE,
  artifact_type VARCHAR(100) NOT NULL,
  name          VARCHAR(255) NOT NULL,
  content       TEXT,
  metadata      JSONB DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_artifacts_agent_id ON agent_artifacts(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_artifacts_workflow_id ON agent_artifacts(workflow_id);
CREATE INDEX IF NOT EXISTS idx_agent_artifacts_type ON agent_artifacts(artifact_type);

-- ─────────────────────────────────────────
-- USER & AUTH TABLES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email         VARCHAR(255) UNIQUE NOT NULL,
  username      VARCHAR(100) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  full_name     VARCHAR(255),
  role          VARCHAR(50) NOT NULL DEFAULT 'user',
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  last_login_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ─────────────────────────────────────────
-- SEED: DEFAULT AGENTS
-- ─────────────────────────────────────────
INSERT INTO agents (agent_id, name, description, role, runtime, capabilities, tools, status) VALUES
  ('architect_agent', 'Architect Agent', 'Designs system architecture, services, and database schemas', 'architect', 'nemo',
   ARRAY['architecture_design', 'system_design', 'database_design', 'api_design'],
   ARRAY['search_tool', 'documentation_tool'], 'HEALTHY'),
  ('planner_agent', 'Planner Agent', 'Breaks down goals into epics, stories, and actionable tasks', 'planner', 'nemo',
   ARRAY['planning', 'task_decomposition', 'estimation', 'roadmapping'],
   ARRAY['planning_tool'], 'HEALTHY'),
  ('developer_agent', 'Developer Agent', 'Writes, refactors, and tests source code', 'developer', 'nemo',
   ARRAY['coding', 'refactoring', 'testing', 'debugging'],
   ARRAY['git_tool', 'filesystem_tool', 'terminal_tool', 'search_tool'], 'HEALTHY'),
  ('reviewer_agent', 'Reviewer Agent', 'Reviews code for quality, security, and best practices', 'reviewer', 'nemo',
   ARRAY['code_review', 'security_analysis', 'quality_assessment'],
   ARRAY['code_analysis_tool'], 'HEALTHY'),
  ('qa_agent', 'QA Agent', 'Creates and runs tests, produces defect reports', 'qa', 'nemo',
   ARRAY['test_creation', 'test_execution', 'defect_reporting', 'performance_testing'],
   ARRAY['test_runner_tool'], 'HEALTHY'),
  ('devops_agent', 'DevOps Agent', 'Manages deployments, containers, and infrastructure', 'devops', 'nemo',
   ARRAY['deployment', 'containerization', 'infrastructure', 'monitoring'],
   ARRAY['docker_tool', 'kubernetes_tool'], 'HEALTHY')
ON CONFLICT (agent_id) DO NOTHING;

-- ─────────────────────────────────────────
-- SEED: DEFAULT ADMIN USER
-- ─────────────────────────────────────────
-- password: Admin@123 (bcrypt hash)
INSERT INTO users (email, username, password_hash, full_name, role) VALUES
  ('admin@factory.local', 'admin', '$2b$12$bz1eUjP7Bhm07qgP//d2Y.eeAItOeuPrIw1S1yLyByeMUVwk8kipW', 'Factory Admin', 'admin')
ON CONFLICT (email) DO NOTHING;
