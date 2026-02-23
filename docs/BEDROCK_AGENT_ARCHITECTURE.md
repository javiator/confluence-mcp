# Bedrock AgentCore: How It All Works

A high-level guide to understanding the architecture of this Confluence MCP agent.

---

## The Big Picture

```
You (Browser)
    │
    ▼
┌──────────────┐       ┌────────────────────┐       ┌─────────────────────┐
│  Chainlit UI │──────▶│  LangGraph Agent   │──────▶│  MCP Server         │
│  (app.py)    │◀──────│  (bedrock_graph.py)│◀──────│  (server.py)        │
└──────────────┘       └────────────────────┘       └─────────────────────┘
                                │                              │
                                ▼                              ▼
                        ┌──────────────┐             ┌─────────────────────┐
                        │ AWS Bedrock  │             │  Confluence REST API │
                        │ Claude       │             │  (Atlassian Cloud)   │
                        └──────────────┘             └─────────────────────┘
```

When you type a message in the browser:
1. **Chainlit** (`app.py`) receives it and starts the LangGraph graph
2. The **LangGraph Agent** (`bedrock_graph.py`) sends your message to **AWS Bedrock Claude**
3. Claude decides what to do and calls a **tool** (e.g. `search_confluence`)
4. The **MCP Client** (`client.py`) forwards that tool call to the **MCP Server** (`server.py`)
5. The MCP Server executes the actual **Confluence REST API** call
6. Results flow back up the chain and Claude summarizes them for you

---

## Key Components

### 1. `server.py` — The MCP Tool Server

This is the brain of the Confluence integration. It exposes Confluence operations as **MCP tools** using the [FastMCP](https://gofastmcp.com) library.

**Key tools exposed:**

| Tool | What it does |
|------|-------------|
| `search_confluence` | Full-text CQL search across pages |
| `get_confluence_page` | Fetch a page's content by ID |
| `get_confluence_children` | List child pages of a given page |
| `execute_confluence_publish` | Create a new page with XHTML content |
| `update_page_full` | Replace an existing page's content |
| `append_to_page` | Append content to an existing page |

**Important detail — Access Control:**
The server reads `config.json` on startup and enforces:
- `allowed_spaces`: Only pages in listed space keys can be created/modified
- `allowed_parents`: Only under specific parent page IDs within each space

This prevents the agent from accidentally creating pages anywhere in your Confluence.

**XHTML Sanitization (`robust_sanitize_confluence_xhtml`):**
LLMs don't always produce perfectly valid Confluence storage format (XHTML). The server has a layered sanitization function that:
- Un-escapes HTML entities (e.g. fixes `&lt;h1&gt;` → `<h1>`)
- Strips outer `<![CDATA[` wrappers if the model wraps the whole payload
- Repairs dangling `<ac:plain-text-body>` tags that swallow headings
- Repairs unclosed `<![CDATA[` blocks inside code macros

---

### 2. `bedrock_graph.py` — The LangGraph Agent

This is the "thinking" layer. It uses [LangGraph](https://langchain-ai.github.io/langgraph/) to build a simple but powerful **ReAct-style agent loop**:

```
START
  │
  ▼
agent_node  ──── has tool_calls? ────YES────▶  tool_node
  ▲                                                │
  └───────────────────────────────────────────────┘
                       NO ──▶ END
```

**`agent_node`:**
- Prepends the `SYSTEM_PROMPT` to the message history
- Calls `repair_history_for_bedrock()` to ensure strict role alternation
  (AWS Bedrock requires: User → Assistant → User → Assistant → …)
- Sends messages to Claude via `ChatBedrock` (LangChain AWS)
- Returns the new `AIMessage` to append to history

**`tool_node`:**
- Reads `tool_calls` from the last `AIMessage`
- Calls each tool through the `MCPClient`
- Returns `ToolMessage` results to append to history

**State:**
```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]  # accumulates history
    reasoning_trace: List[str]                             # shows steps in UI
```

The `add_messages` reducer (from LangGraph) ensures messages are **appended**, not replaced, on each graph step. Without this, tool results would have no corresponding tool call to reference and Bedrock would reject them.

**Key lesson — Bedrock Role Rules:**
AWS Bedrock's Converse API is very strict:
- Messages must strictly alternate: `user` → `assistant` → `user` → ...
- Every `tool_result` block **must** have a matching `tool_use` block in the message immediately before it
- The `repair_history_for_bedrock()` function enforces these rules defensively

---

### 3. `llm.py` — The LLM Factory

A simple factory function `get_llm(provider, model)` that returns the right LangChain `ChatModel` based on environment variables.

Supported providers: `bedrock`, `openai`, `anthropic`, `google`, `ollama`

This makes it easy to swap between models for testing — just change `LLM_PROVIDER` in `.env`.

Currently active: **AWS Bedrock → Claude 3.5 Sonnet** (`us.anthropic.claude-3-5-sonnet-20241022-v2:0`)
with `max_tokens=8192` to handle large page content in a single response.

---

### 4. `client.py` — The MCP Client

Launches the MCP server as a **subprocess** over stdio (standard input/output) and manages the connection.

```python
# server_params tells the MCP client to run server.py as a subprocess
server_params = StdioServerParameters(
    command=sys.executable,
    args=["-m", "src.confluence_mcp"],
    env=os.environ.copy()
)
```

Key methods:
- `connect()` — starts the subprocess and initializes the MCP session
- `call_tool(name, arguments)` — sends a tool call and returns the text result
- `get_tools()` — returns the cached list of available tools (used by `bedrock_graph.py` to tell Claude what it can do)
- `close()` — shuts down the subprocess cleanly

---

### 5. `app.py` — The Chainlit UI

The chat interface. Key events:

| Event | What happens |
|-------|-------------|
| `on_chat_start` | Initialises the `MCPClient`, creates the LangGraph app, sets up session memory |
| `on_message` | Runs the LangGraph graph for the user's message, streams reasoning steps as collapsible "Agent Reasoning" blocks, sends final AI response |
| `on_chat_end` | Saves conversation history to `MemoryStore`, closes MCP connection |

**Response Display:**
The graph streams `values` (full state snapshots after each node). The app scans each snapshot for the latest `AIMessage` without `tool_calls` — that's the final human-readable response. Bedrock returns content as either:
- A plain string: `"Here are the results..."`
- A list of blocks: `[{"type": "text", "text": "Here are the results..."}]`

Both formats are handled, and the extracted text is sent as a `cl.Message` after the stream completes.

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `CONFLUENCE_BASE_URL` | e.g. `https://yourco.atlassian.net/wiki` |
| `CONFLUENCE_EMAIL` | Your Atlassian account email |
| `CONFLUENCE_API_TOKEN` | API token from https://id.atlassian.com/manage-profile/security/api-tokens |
| `LLM_PROVIDER` | `bedrock` (or `openai`, `anthropic`, etc.) |
| `AWS_REGION` | e.g. `us-east-1` |
| `AWS_PROFILE` | (optional) named profile from `~/.aws/credentials` |

---

## Request Flow Walk-Through

**Example: "Find me pages about Ubuntu"**

1. `app.py` receives `HumanMessage("Find me pages about Ubuntu")`
2. `bedrock_graph.py` sends `[SystemMessage, HumanMessage]` to Claude
3. Claude responds with `AIMessage(tool_calls=[{"name": "search_confluence", "args": {"query": "Ubuntu"}}])`
4. `tool_node` calls `mcp_client.call_tool("search_confluence", {"query": "Ubuntu"})`
5. `client.py` sends the call over stdio to `server.py`
6. `server.py` executes: `GET /rest/api/content/search?cql=text~"Ubuntu" AND space in ("AR")...`
7. Confluence returns a list of matching pages as JSON
8. Results flow back as a `ToolMessage` appended to history
9. Claude sees the results and writes a human-friendly summary
10. `app.py` extracts the final text and calls `cl.Message(...).send()`

---

## Why MCP?

**Model Context Protocol (MCP)** is an open standard (by Anthropic) that lets AI models discover and call tools in a standardized way — similar to how HTTP standardizes web communication.

**Benefits in this project:**
- **Separation of concerns**: The Confluence logic (`server.py`) is completely decoupled from the agent logic
- **Reusability**: Any MCP-compatible client (Claude Desktop, Cursor, etc.) could use the same `server.py`
- **Discoverability**: The agent automatically knows what tools are available via `list_tools()`
- **Transport flexibility**: Currently uses stdio subprocess; could switch to HTTP/SSE for remote deployment

---

## Development Quick-Reference

```bash
# Start the Chainlit UI
./start_agent.sh

# Headless agent test (no UI)
.venv/bin/python3 test_agent_direct.py "Your prompt here"

# Direct Confluence API test
.venv/bin/python3 -c "
import requests, os
from dotenv import load_dotenv
load_dotenv()
print(requests.get(
    f'{os.getenv(\"CONFLUENCE_BASE_URL\")}/rest/api/content/search',
    auth=(os.getenv('CONFLUENCE_EMAIL'), os.getenv('CONFLUENCE_API_TOKEN')),
    params={'cql': 'text~\"ubuntu\" AND space=\"AR\"', 'limit': 5}
).json())
"
```
