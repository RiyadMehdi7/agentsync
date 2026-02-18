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

## Features

- **File Locking** — Exclusive locks prevent simultaneous edits to the same files
- **Work Tracking** — See what every agent is working on across your team
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
