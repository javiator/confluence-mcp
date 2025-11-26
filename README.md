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

## Installation

### Option 1: Install via pip (Recommended)

You can install the package directly if you have it locally or from a git repo:

```bash
pip install .
```

### Option 2: Install via uv (Fastest)

If you use [uv](https://github.com/astral-sh/uv), you can install dependencies and run the project efficiently.

```bash
uv pip install .
```

### Option 3: Run from source

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: `requirements.txt` is provided for convenience, but `pyproject.toml` is the source of truth.*

## Configuration

### 1. Environment Variables

The server requires the following environment variables for authentication:

*   `CONFLUENCE_BASE_URL`: Base URL of your Confluence instance (e.g., `https://your-domain.atlassian.net/wiki`).
*   `CONFLUENCE_EMAIL`: Your Atlassian account email.
*   `CONFLUENCE_API_TOKEN`: Your Atlassian API token.

For the **Agent**, you also need LLM keys:
*   `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY`.

### 2. Access Control (`config.json`)

Create a `config.json` file in the directory where you will run the server. You can copy `config.example.json` as a starting point.

```json
{
  "allowed_spaces": ["AR", "ENG", "KB"],
  "allowed_parents": {
    "AR": ["2424881", "2490466"],
    "ENG": ["223344"],
    "KB": ["998877"]
  }
}
```

*   **allowed_spaces**: List of space keys the AI can access.
*   **allowed_parents**: Dictionary mapping space keys to a list of Page IDs.
    *   **For Creation**: New pages can *only* be created as children of these IDs.
    *   **For Search**: Search results are restricted to *only* these IDs.

The server looks for `config.json` in the following order:
1.  Path specified by `CONFLUENCE_MCP_CONFIG` environment variable.
2.  Current working directory.
3.  Package directory (fallback).

## Usage

### Running the MCP Server

**Standard:**
```bash
confluence-mcp
```

**With uv:**
```bash
uv run confluence-mcp
```

### Running the Conversational Agent

This project includes a **Chainlit** agent that connects to the MCP server.

**Standard:**
```bash
chainlit run src/confluence_mcp/agent/app.py -w
```

**With uv:**
```bash
uv run chainlit run src/confluence_mcp/agent/app.py -w
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
