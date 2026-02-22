#!/bin/bash
# start_mcp_tunnel.sh
# Starts the local MCP Streamable HTTP server and a Cloudflare Tunnel

echo "Starting Confluence MCP Server (HTTP) on port 8000..."
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"
uvicorn confluence_mcp.http_server.fastapi_server:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

# Wait a moment for the server to start
sleep 2

echo "Starting Cloudflare Tunnel to expose localhost:8000..."
echo "=========================================================="
echo "⚠️  Look for the 'https://trycloudflare.com' URL below ⚠️"
echo "=========================================================="
cloudflared tunnel --url http://127.0.0.1:8000
# Cleanup trap
trap "kill $SERVER_PID" EXIT
