-- Agents table
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL UNIQUE,
    agent_type TEXT NOT NULL DEFAULT 'unknown',
    user_id TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id);

-- File locks table
CREATE TABLE IF NOT EXISTS file_locks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    description TEXT,
    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    released_at TIMESTAMP,
    status TEXT DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_locks_file_path ON file_locks(file_path);
CREATE INDEX IF NOT EXISTS idx_locks_agent_id ON file_locks(agent_id);
CREATE INDEX IF NOT EXISTS idx_locks_status ON file_locks(status);

-- Work items table
CREATE TABLE IF NOT EXISTS work_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    description TEXT NOT NULL,
    files TEXT,
    status TEXT DEFAULT 'in_progress',
    priority INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    commit_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_work_agent_id ON work_items(agent_id);
CREATE INDEX IF NOT EXISTS idx_work_status ON work_items(status);

-- Agent actions table (for semantic conflict detection)
CREATE TABLE IF NOT EXISTS agent_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    files TEXT NOT NULL,
    intent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    work_item_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_actions_agent_id ON agent_actions(agent_id);
CREATE INDEX IF NOT EXISTS idx_actions_created_at ON agent_actions(created_at);

-- Conflicts table
CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    agent1_id TEXT NOT NULL,
    agent2_id TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    severity TEXT,
    description TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution_strategy TEXT,
    status TEXT DEFAULT 'open'
);

CREATE INDEX IF NOT EXISTS idx_conflicts_status ON conflicts(status);
CREATE INDEX IF NOT EXISTS idx_conflicts_file ON conflicts(file_path);

-- Event log (for debugging and analytics)
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    agent_id TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_type ON event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON event_log(created_at);
