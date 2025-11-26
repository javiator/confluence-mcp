#!/bin/bash
# Confluence MCP Agent Launcher
# This script starts the Chainlit agent with the correct parameters

cd "$(dirname "$0")"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start Chainlit with remote access enabled
uv run chainlit run src/confluence_mcp/agent/app.py -w --host 0.0.0.0 --port 8000
