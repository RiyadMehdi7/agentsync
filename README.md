# AgentSync MCP

**Real-time coordination for AI coding agents via Model Context Protocol**

When multiple developers use different AI coding agents (Cursor, Claude Code, Aider, etc.) on the same codebase, AgentSync prevents conflicting changes through a shared lock registry and intelligent conflict detection.

## Quick Start

```bash
# Install
pip install agentsync-mcp

# Initialize database
agentsync-mcp init

# Start server
agentsync-mcp start
```

No API keys are required for core coordination (auto-detected sessions, file locks, work tracking).
`ANTHROPIC_API_KEY` is only needed if you want AI conflict analysis / merge suggestions.

## Auto-Coordination Mode (Zero Config)

Wrap your agent CLI so AgentSync automatically detects file changes and acquires/releases locks.

```bash
# Codex (recommended shortcut)
agentsync-mcp codex

# Claude (recommended shortcut)
agentsync-mcp claude

# Generic wrapper (any command)
agentsync-mcp auto --client codex -- codex
agentsync-mcp auto --client claude -- claude
```

How it works:
- launches the agent CLI
- assigns a shared AgentSync session ID (used by the MCP server and wrapper)
- polls `git status` for changed files
- baselines existing dirty files, then auto-acquires locks for new changes made during the session
- renews locks while the session is active
- auto-releases wrapper-acquired locks when files are cleaned or the session exits

## Features

- **File Locking** — Exclusive locks prevent simultaneous edits to the same files
- **Work Tracking** — See what every agent is working on across your team
- **Session Auto-Detection** — Detects connected Claude/Codex/Cursor/Aider sessions automatically
- **Conflict Detection** — LLM-powered semantic analysis warns about incompatible changes
- **Merge Suggestions** — AI-generated merge strategies with confidence scores
- **Zero Config** — MCP-compatible agents pick up tools automatically

## Client Setup

### Claude Code

Add to `~/.claude/config.json`:

```json
{
  "mcpServers": {
    "agentsync": {
      "command": "uvx",
      "args": ["agentsync-mcp"]
    }
  }
}
```

### Cursor

Add to `.cursor/config.json`:

```json
{
  "mcp": {
    "servers": {
      "agentsync": {
        "type": "stdio",
        "command": "uvx",
        "args": ["agentsync-mcp"]
      }
    }
  }
}
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `request_file_lock` | Claim exclusive access to files before editing |
| `release_file_lock` | Release locks when done |
| `check_file_status` | See if files are available |
| `get_active_work` | List what all agents are working on |
| `get_active_sessions` | List live auto-detected agent sessions (Claude/Codex/etc.) |
| `register_agent_action` | Register changes for conflict detection |
| `get_conflict_suggestions` | Get AI merge strategies for conflicts |

## Development

```bash
git clone https://github.com/yourusername/agentsync-mcp.git
cd agentsync-mcp
pip install -e ".[dev]"
agentsync-mcp init
pytest
```

## License

MIT
