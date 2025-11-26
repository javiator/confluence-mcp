# Confluence MCP Server

A Model Context Protocol (MCP) server for Atlassian Confluence. This server provides tools to search, read, create, and update Confluence pages, with built-in access controls for safe AI interactions.

## Features

- **Search**: Find pages using Confluence Query Language (CQL), automatically filtered by allowed spaces and specific page IDs.
- **Read**: Retrieve page content as both plain text (for reasoning) and storage format (HTML, for editing).
- **Create**: Create new pages in whitelisted spaces and under specific parent pages. Automatically applies the `ai-managed` label.
- **Update**: Safely update pages. Enforces that pages must have the `ai-managed` or `ai-generated` label to be modifiable.
- **Smart Merge**: Helper tool to fetch context for merging updates into existing pages.
- **Configurable Access Control**: Permissions are defined in `config.json`, not hardcoded.

## Tools

1.  `search_confluence(query: str)`
    *   Search for pages in allowed spaces.
    *   **Restricted**: Results are filtered to match `ALLOWED_SPACES` and, if defined, specific page IDs in `ALLOWED_PARENTS`.

2.  `get_confluence_page(page_id: str)`
    *   Get page content.
    *   Returns both `textContent` (clean text) and `storageContent` (raw HTML).

3.  `create_confluence_page(space_key: str, parent_id: str, title: str, body: str)`
    *   Create a new page (HTML body).
    *   **Restricted**: Must be in `ALLOWED_SPACES` and under `ALLOWED_PARENTS`.
    *   **Labeling**: Automatically adds the `ai-managed` label.

4.  `update_confluence_page_full(page_id: str, body: str)`
    *   Overwrite a page's body.
    *   **Restricted**: Page must be in `ALLOWED_SPACES` AND have `ai-generated` or `ai-managed` label.

5.  `prepare_confluence_page_merge_update(page_id: str)`
    *   Get page content + metadata to help LLMs prepare a merge.

## Configuration

### Environment Variables
The server requires the following environment variables for authentication:

*   `CONFLUENCE_BASE_URL`: Base URL of your Confluence instance (e.g., `https://your-domain.atlassian.net/wiki`).
*   `CONFLUENCE_EMAIL`: Your Atlassian account email.
*   `CONFLUENCE_API_TOKEN`: Your Atlassian API token.

### Access Control (`config.json`)
Permissions are managed in `config.json` located in the same directory as `server.py`.

```json
{
  "allowed_spaces": ["AR", "ENG", "KB"],
  "allowed_parents": {
    "AR": ["2424881", "2490466", "5678", "41058315"],
    "ENG": ["223344"],
    "KB": ["998877"]
  }
}
```

*   **allowed_spaces**: List of space keys the AI can access.
*   **allowed_parents**: Dictionary mapping space keys to a list of Page IDs.
    *   **For Creation**: New pages can *only* be created as children of these IDs.
    *   **For Search**: Search results are restricted to *only* these IDs (and their children, if the search logic is extended, currently strict ID check).

## Installation & Usage

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure Permissions**:
    Edit `config.json` to define your allowed spaces and parent pages.

3.  **Run the Server**:
    ```bash
    export CONFLUENCE_BASE_URL="https://your-domain.atlassian.net/wiki"
    export CONFLUENCE_EMAIL="user@example.com"
    export CONFLUENCE_API_TOKEN="your-api-token"
    
    python server.py
    ```

## License

[MIT](https://choosealicense.com/licenses/mit/)
