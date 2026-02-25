# Confluence MCP Server

A Model Context Protocol (MCP) server for Atlassian Confluence. This server provides tools to search, read, create, and update Confluence pages, with built-in access controls for safe AI interactions.

## Features

- **Search**: Find pages using Confluence Query Language (CQL), automatically filtered by allowed spaces and specific page IDs.
- **Read**: Retrieve page content as both plain text (for reasoning) and storage format (HTML, for editing).
- **Create**: Create new pages in whitelisted spaces and under specific parent pages. Automatically applies the `ai-managed` label.
- **Update**: Safely update pages. Enforces that pages must have the `ai-managed` or `ai-generated` label to be modifiable.
- **Smart Merge**: Helper tool to fetch context for merging updates into existing pages.
- **Get Children**: Retrieve direct child pages of a specific page. Useful for navigating the hierarchy when search is unreliable.
- **Configurable Access Control**: Permissions are defined in `config.json`, not hardcoded.

- **Cloud-Native**: Powered by **AWS Bedrock AgentCore** for managed multi-agent orchestration.
- **Search**: Find pages using Confluence Query Language (CQL), with improved logic for complex queries.
- **Read/Write/Update**: Full CRUD capabilities with safety checks (AI-managed labels).
- **Session Memory**: Persistent conversation history across AWS Lambda restarts.
- **Cost Optimized**: Dynamic support for Claude 3 Haiku and Amazon Nova Lite.

## 📚 Documentation Guides

For detailed instructions, see the dedicated documentation:
- **[Usage & Deployment Guide](docs/USAGE_GUIDE.md)**: How to deploy from scratch, useful AgentCore CLI commands, daily usage, and complete AWS teardown instructions.
- **[AgentCore Architecture](docs/BEDROCK_AGENT_ARCHITECTURE.md)**: Deep dive into the cloud-native routing and design.
- **[AgentCore Manual Setup](docs/AGENTCORE_SETUP.md)**: Manual AWS console steps and troubleshooting for the hosted runtime.

## ☁️ Architecture: AWS Bedrock AgentCore

The project has transitioned to a high-performance, cloud-native architecture. 

1. **MCP Server**: Containerized Lambda function serving as the "Action Group" for Bedrock.
2. **Bedrock AgentCore**: Hosted runtime orchestrating the agent logic and memory.
3. **Chainlit UI**: Local/Remote frontend that communicates with the cloud runtime.

**Key Components:**
- **[server.py](src/confluence_mcp/server.py)**: The core MCP tool definitions.
- **[agentcore_server.py](src/confluence_mcp/http_server/agentcore_server.py)**: The FastAPI wrapper for AWS Lambda integration.
- **[app.py](src/confluence_mcp.chat_app/app.py)**: The Chainlit frontend.

## 🚀 Getting Started

### 1. Prerequisites
- AWS Account with Bedrock access.
- Confluence API Token.
- Python 3.10+ (recommend using `uv`).

### 2. Configuration
Create a `.env` file from `.env.example`:
```bash
USE_AGENTCORE=true
AGENTCORE_AGENT_ID=arn:aws:bedrock-agentcore:...
CONFLUENCE_GATEWAY_URL=https://...
```

### 3. Launching the UI
The easiest way to start the system is via the launcher script:
```bash
./start_agent.sh
```
This launches the Chainlit interface on `http://localhost:8000`.

---

## 🛠️ Deployment

To deploy the MCP server to AWS:
```bash
./scripts/deploy_agentcore_mcp.sh
```
This builds the Docker image, pushes it to ECR, and updates the Lambda function.

To update the AgentCore agent logic or environment variables:
```bash
cd agentcore_runtime
agentcore deploy --env BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

### Connecting to an MCP Client

You can use this server with any MCP-compatible client (Claude Desktop, Cursor, etc.).

#### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "confluence": {
      "command": "uv",
      "args": ["run", "confluence-mcp"],
      "env": {
        "CONFLUENCE_BASE_URL": "https://your-domain.atlassian.net/wiki",
        "CONFLUENCE_EMAIL": "user@example.com",
        "CONFLUENCE_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

#### Cursor

1.  Go to **Settings** > **MCP**.
2.  Click **Add New MCP Server**.
3.  **Name**: `confluence` (or any name you prefer).
4.  **Type**: `command`.
5.  **Command**: `uv run confluence-mcp` (ensure you are in the project directory or provide the full path to `uv` and the project).
6.  **Environment Variables**: Add your `CONFLUENCE_...` keys here.

## License

[MIT](https://choosealicense.com/licenses/mit/)
