-- SQLite schema for Agent Orchestration System
-- Optimized for fast queries with appropriate indexes

-- Agents table: stores agent state and metadata
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    capabilities TEXT NOT NULL,  -- JSON: {capability: proficiency}
    specializations TEXT NOT NULL,  -- JSON: {task_type: score}
    created_at TEXT NOT NULL,
    last_active TEXT NOT NULL,
    total_tasks INTEGER NOT NULL DEFAULT 0,
    successful_tasks INTEGER NOT NULL DEFAULT 0,
    metadata TEXT NOT NULL  -- JSON: additional metadata
);

-- Index for querying active agents (most common query)
CREATE INDEX IF NOT EXISTS idx_agents_status 
ON agents(status);

-- Index for querying by last activity (for cleanup)
CREATE INDEX IF NOT EXISTS idx_agents_last_active 
ON agents(last_active);

-- Performance records table: stores task execution history
CREATE TABLE IF NOT EXISTS performance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    success INTEGER NOT NULL,  -- 0 or 1 (SQLite boolean)
    completion_time_ms REAL NOT NULL,
    resource_usage TEXT NOT NULL,  -- JSON: {resource: value}
    timestamp TEXT NOT NULL,
    error_message TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Index for querying agent performance (most common query)
CREATE INDEX IF NOT EXISTS idx_performance_agent_task_type 
ON performance_records(agent_id, task_type, timestamp DESC);

-- Index for querying by task
CREATE INDEX IF NOT EXISTS idx_performance_task 
ON performance_records(task_id);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_performance_timestamp 
ON performance_records(timestamp DESC);

-- Evolution events table: stores agent evolution history
CREATE TABLE IF NOT EXISTS evolution_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    agent_ids TEXT NOT NULL,  -- JSON: list of agent IDs
    reason TEXT NOT NULL,
    details TEXT NOT NULL,  -- JSON: event details
    timestamp TEXT NOT NULL,
    synced_to_github INTEGER NOT NULL DEFAULT 0  -- 0 or 1 (SQLite boolean)
);

-- Index for querying unsynced events
CREATE INDEX IF NOT EXISTS idx_evolution_synced 
ON evolution_events(synced_to_github, timestamp);

-- Index for querying by event type
CREATE INDEX IF NOT EXISTS idx_evolution_type 
ON evolution_events(event_type, timestamp DESC);

-- Tasks table: stores task state and assignments
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    task_type TEXT NOT NULL,
    requirements TEXT NOT NULL,  -- JSON: task requirements
    success_criteria TEXT NOT NULL,  -- JSON: list of criteria
    priority INTEGER NOT NULL DEFAULT 5,
    dependencies TEXT NOT NULL,  -- JSON: list of task IDs
    parent_task_id TEXT,
    assigned_agent_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    result TEXT,  -- JSON: task result
    metadata TEXT NOT NULL,  -- JSON: additional metadata
    FOREIGN KEY (assigned_agent_id) REFERENCES agents(id),
    FOREIGN KEY (parent_task_id) REFERENCES tasks(id)
);

-- Index for querying pending tasks
CREATE INDEX IF NOT EXISTS idx_tasks_status 
ON tasks(status, priority DESC);

-- Index for querying by assigned agent
CREATE INDEX IF NOT EXISTS idx_tasks_agent 
ON tasks(assigned_agent_id, status);

-- Index for querying sub-tasks
CREATE INDEX IF NOT EXISTS idx_tasks_parent 
ON tasks(parent_task_id);

-- Task assignments table: tracks assignment history
CREATE TABLE IF NOT EXISTS task_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Index for querying assignment history
CREATE INDEX IF NOT EXISTS idx_assignments_task 
ON task_assignments(task_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_assignments_agent 
ON task_assignments(agent_id, timestamp DESC);

-- Delegation chains table: tracks agent-to-agent delegation
CREATE TABLE IF NOT EXISTS delegation_chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    from_agent_id TEXT NOT NULL,
    to_agent_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (from_agent_id) REFERENCES agents(id),
    FOREIGN KEY (to_agent_id) REFERENCES agents(id)
);

-- Index for querying delegation chains
CREATE INDEX IF NOT EXISTS idx_delegation_task 
ON delegation_chains(task_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_delegation_from 
ON delegation_chains(from_agent_id, timestamp DESC);

-- Agent communication table: tracks inter-agent communication
CREATE TABLE IF NOT EXISTS agent_communications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent_id TEXT NOT NULL,
    to_agent_id TEXT NOT NULL,
    communication_type TEXT NOT NULL,
    content TEXT NOT NULL,  -- JSON: communication content
    timestamp TEXT NOT NULL,
    FOREIGN KEY (from_agent_id) REFERENCES agents(id),
    FOREIGN KEY (to_agent_id) REFERENCES agents(id)
);

-- Index for querying communication history
CREATE INDEX IF NOT EXISTS idx_communication_agents 
ON agent_communications(from_agent_id, to_agent_id, timestamp DESC);

-- System metrics table: stores system-wide metrics
CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    timestamp TEXT NOT NULL
);

-- Index for querying metrics by name
CREATE INDEX IF NOT EXISTS idx_metrics_name 
ON system_metrics(metric_name, timestamp DESC);
