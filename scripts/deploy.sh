#!/usr/bin/env bash
set -euo pipefail

echo "Deploying AgentSync MCP to fly.io..."

# Ensure fly CLI is available
if ! command -v fly &> /dev/null; then
    echo "Error: fly CLI not found. Install from https://fly.io/docs/flyctl/install/"
    exit 1
fi

# Deploy
fly deploy

echo "Deployment complete!"
fly status
