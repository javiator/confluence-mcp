# Multi-Session Chat History

The Confluence MCP Agent now supports **persistent chat history** across multiple sessions, allowing you to maintain and resume previous conversations.

## Features

### 1. **Automatic Conversation Persistence**
- Every conversation is automatically saved to a local SQLite database
- Each session has a unique ID and maintains full message history
- Conversations are saved in real-time as you chat

### 2. **Browse Past Conversations**
Three ways to access your chat history:

#### Option A: Chainlit History Sidebar (Recommended)
1. Look for the **🕐 history icon** in the Chainlit sidebar
2. Click it to see all your previous conversations
3. Click any conversation to resume it with full context

#### Option B: Built-in Session Browser
1. Click the **"📜 Browse Past Conversations"** starter button
2. Or type `/list_sessions` in any chat
3. View a list of your recent conversations with:
   - Session ID
   - Creation date
   - Last update time
   - Message count

#### Option C: Direct Database Access
The chat history is stored in:
- **Chainlit UI:** `./chainlit_history.db` (Chainlit's native storage)
- **Agent Memory:** `./confluence_memory.db` (Agent's internal memory)

### 3. **Resume Previous Conversations**
When you resume a chat:
- Full conversation history is restored
- Agent remembers all context from the previous session
- You can continue exactly where you left off

## Configuration

### Database Location
Edit `.chainlit/config.toml` to change the database path:

```toml
[data]
data_persistence = true
database_url = "sqlite:///./chainlit_history.db"  # Change path here
```

For production environments, use PostgreSQL:
```toml
database_url = "postgresql://user:password@localhost/chainlit_db"
```

### Session Timeout
Sessions are kept alive for 1 hour by default:
```toml
[project]
session_timeout = 3600  # seconds
```

## Architecture

The system maintains two storage layers:

1. **Chainlit Data Layer** (`chainlit_history.db`)
   - Stores UI-level thread metadata
   - Enables the Chainlit sidebar history browser
   - Managed by Chainlit framework

2. **Agent Memory Store** (`confluence_memory.db`)
   - Stores full conversation messages (LangChain format)
   - Includes session metadata (model, timestamps, etc.)
   - Managed by `MemoryStore` class

Both layers are synchronized to ensure consistent history across UI and agent logic.

## Usage Examples

### Starting a New Chat
Just click "New Chat" - the previous conversation is automatically saved.

### Resuming a Chat
1. Click the history icon (🕐) in the sidebar
2. Select a previous conversation
3. The agent will load all previous messages and context

### Viewing All Sessions Programmatically
```python
from confluence_mcp.agent.memory import MemoryStore

store = MemoryStore()
sessions = store.list_sessions()

for session in sessions:
    print(f"Session {session['id']}: {session['message_count']} messages")
```

### Loading a Specific Session
```python
history = store.load_session(session_id)
print(f"Loaded {len(history)} messages")
```

## Technical Details

### Session Lifecycle
1. **Creation:** New session ID generated on `@cl.on_chat_start`
2. **Updates:** Messages saved after each exchange
3. **Resume:** Full history loaded on `@cl.on_chat_resume`
4. **Cleanup:** Final save on `@cl.on_chat_end`

### Message Format
Messages are stored as LangChain `BaseMessage` objects:
- `HumanMessage`: User inputs
- `AIMessage`: Agent responses
- `ToolMessage`: Tool execution results (internal)

### Storage Schema (Agent Memory)
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    messages_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    message_count INTEGER NOT NULL
);
```

## Troubleshooting

### "No previous conversations found"
- Start a new chat and send at least one message
- Sessions are created after the first message exchange

### Can't see history in sidebar
- Ensure `data_persistence = true` in `.chainlit/config.toml`
- Check that `chainlit_history.db` exists in project root
- Restart the Chainlit server

### Sessions not resuming correctly
- Check for errors in terminal/logs
- Verify both databases exist and are not corrupted
- Try deleting databases and starting fresh (⚠️ loses all history)

## Future Enhancements

Potential improvements for multi-session support:
- [ ] Session tagging and search
- [ ] Export conversations to markdown/JSON
- [ ] Session analytics (most active topics, etc.)
- [ ] Session merging/branching
- [ ] Cloud sync for multi-device access
