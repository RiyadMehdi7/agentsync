#!/usr/bin/env bash
set -euo pipefail

echo "Setting up AgentSync MCP..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Copy .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit it to add your ANTHROPIC_API_KEY"
fi

# Initialize database
agentsync-mcp init

echo ""
echo "Setup complete! Run: agentsync-mcp start"
