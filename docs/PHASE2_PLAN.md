# Phase 2: Intelligence & Memory — Plan

> **Goal**: Give the agent system memory that persists across sessions and intelligence that understands conversational context

**Branch**: `claude/phase-2-ceArC`
**Estimated Duration**: 1 week
**Prerequisite**: Phase 1 Complete ✅

---

## 🧠 What This Phase Is About

Phase 1 agents are **stateless** — every new conversation starts with a blank slate.

```
Session A:  User: "Update the API docs page (ID: 12345)"
            Agent: ✅ updates page 12345

Session B:  User: "Update that page again"
            Agent: ❌ "Which page? I don't know what you mean."
```

Phase 2 fixes this with two capabilities:

1. **Memory** — agents remember past interactions, pages worked on, user preferences
2. **Intelligence** — agents understand context clues like "that page", "it", "the same space"

---

## 📦 Phase 2 Breakdown

### Phase 2.1 — Conversation Memory (days 1–3)

**Goal**: Persist conversations across restarts. Pick up where you left off.

#### What We Build

A `MemoryStore` backed by SQLite that saves/loads the `messages` list between sessions.

**Concept**:
```
Session A ends → messages saved to SQLite (session_id → messages)
Session B starts → messages loaded from SQLite → agent has full history
```

#### Changes to `AgentState`

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next: str
    active_agent: str
    pending_tool_call: Optional[dict]
    review_status: Optional[str]
    revision_count: int

    # NEW in Phase 2.1
    session_id: str           # unique ID per conversation thread
```

#### New File: `src/confluence_mcp/agent/memory.py`

```python
class MemoryStore:
    """SQLite-backed conversation persistence."""

    def save_session(self, session_id: str, messages: list) -> None:
        """Serialize and save messages to DB."""

    def load_session(self, session_id: str) -> list:
        """Load messages for a session. Returns [] if not found."""

    def list_sessions(self) -> list[dict]:
        """Return summary of all saved sessions (id, last_active, message_count)."""

    def delete_session(self, session_id: str) -> None:
        """Delete a session from DB."""
```

**Storage location**: `~/.confluence_mcp/memory.db` (user's home dir, persists across runs)

#### Chainlit Integration (`app.py`)

- On chat start: generate/assign `session_id`, load history from `MemoryStore`
- On chat end / message send: save updated messages to `MemoryStore`
- UI: show "Resuming session from [date]" banner if history was found

#### Learning Goal
> Understand **serialization**: LangChain `BaseMessage` objects must be converted to plain dicts (JSON) for storage, then deserialized back. This teaches you about object lifecycles and persistence patterns.

---

### Phase 2.2 — Entity Tracking & Resolution (days 3–5)

**Goal**: Agents understand "that page", "it", "the same space" by tracking entities mentioned in conversation.

#### The Problem

```
User: "Find the deployment runbook"
Agent: Found it — "Deployment Runbook" (ID: 98765, Space: ENG)

User: "Now update it to add a new step"
Agent: ❌ Calls update_confluence_page_full with no page ID — it forgot!
```

#### The Solution — Entity Context in State

```python
class AgentState(TypedDict):
    # ... existing fields ...

    # NEW in Phase 2.2
    known_entities: dict   # {"last_page": {"id": "98765", "title": "...", "space": "ENG"},
                           #  "last_space": "ENG",
                           #  "pages": [{"id": ..., "title": ..., "space": ...}]}
```

#### How It Works

**Step 1 — SearchAgent extracts entities**:
After every search/fetch, `SearchAgent` writes the found page(s) into `known_entities`.

```python
# After search_confluence or get_confluence_page returns results:
updates["known_entities"] = {
    "last_page": {"id": "98765", "title": "Deployment Runbook", "space": "ENG"},
    "last_space": "ENG",
    "pages": [...]   # rolling list of recent pages
}
```

**Step 2 — Supervisor injects entity context into routing prompt**:

```python
# In supervisor_node:
if state.get("known_entities"):
    ents = state["known_entities"]
    if ents.get("last_page"):
        p = ents["last_page"]
        context_msg += f"\n[Context: Last page worked on: '{p['title']}' (ID: {p['id']}, Space: {p['space']})]"
```

**Step 3 — WriterAgent uses entity context**:

The WriterAgent's system prompt receives entity context, so "update it" correctly resolves to the last page ID.

#### Example Flow After Phase 2.2

```
User: "Find the deployment runbook"
→ SearchAgent finds page (ID: 98765)
→ Saves to known_entities.last_page

User: "Now update it to add a rollback step"
→ Supervisor sees: [Context: Last page: 'Deployment Runbook' (ID: 98765)]
→ Routes to WriterAgent with entity context
→ WriterAgent correctly updates page 98765 ✅
```

#### Learning Goal
> Understand **context propagation**: how information flows through a stateful graph. The `known_entities` dict is like a shared whiteboard — agents read and write to it as they work.

---

### Phase 2.3 — User Preferences (days 5–7)

**Goal**: Remember simple user preferences so the agent adapts over time.

#### What Gets Remembered

```json
{
  "preferred_space": "ENG",
  "preferred_format": "detailed",
  "default_parent_page": "12345",
  "tone": "technical"
}
```

#### How It Works

- Preferences stored in `~/.confluence_mcp/preferences.json` (simple JSON file)
- Loaded at startup, injected into agent prompts as context
- Updated when user explicitly states preferences ("always use the ENG space", "keep it brief")

#### New File: `src/confluence_mcp/agent/preferences.py`

```python
class UserPreferences:
    def load(self) -> dict: ...
    def save(self, prefs: dict) -> None: ...
    def update(self, key: str, value: str) -> None: ...
```

#### Supervisor Integration

```python
# Preferences injected as context for supervisor:
if prefs.get("preferred_space"):
    context_msg += f"\n[User prefers Space: {prefs['preferred_space']}]"
```

#### Learning Goal
> Understand **personalization**: how a generic agent becomes user-specific. Preferences are the simplest form of long-term learning — no ML needed, just remembering explicit user statements.

---

## 🗂️ File Changes Summary

```
src/confluence_mcp/agent/
├── graph.py          # Update AgentState, inject entity context + preferences into prompts
├── app.py            # Session ID management, load/save memory on start/end
├── memory.py         # NEW: SQLite-backed MemoryStore
├── preferences.py    # NEW: JSON-backed UserPreferences
├── client.py         # Unchanged
└── llm.py            # Unchanged

tests/
├── test_phase2.py    # NEW: Phase 2 tests
└── ...               # Existing tests unchanged

~/.confluence_mcp/    # NEW: user data directory
├── memory.db         # Conversation history (SQLite)
└── preferences.json  # User preferences (JSON)
```

---

## 🧪 Tests (`tests/test_phase2.py`)

### Memory Tests
1. `test_memory_store_save_and_load` — save messages, load them back, verify content
2. `test_memory_store_empty_session` — load non-existent session returns `[]`
3. `test_memory_store_list_sessions` — list sessions returns correct metadata
4. `test_memory_store_delete_session` — delete removes session from DB

### Entity Tracking Tests
5. `test_agent_state_has_known_entities` — `known_entities` in AgentState schema
6. `test_entity_context_in_supervisor_prompt` — entity info injected into supervisor context
7. `test_known_entities_structure` — validates expected shape (`last_page`, `last_space`, `pages`)

### User Preferences Tests
8. `test_preferences_load_defaults` — returns empty/default prefs when no file exists
9. `test_preferences_save_and_load` — save a pref, reload it, verify round-trip
10. `test_preferences_injected_into_context` — preferences appear in agent context

---

## 📊 Success Criteria

| Criteria | How to Verify |
|----------|--------------|
| Conversation persists across restarts | Stop app, restart, messages are still there |
| "Update it" resolves correctly | Search a page, then say "update it" — no clarification needed |
| Preferred space remembered | Say "always use ENG space", then create a page — ENG used automatically |
| All Phase 2 tests pass | `pytest tests/test_phase2.py -v` |
| Phase 1 tests still pass | `pytest tests/test_phase1.py -v` |

---

## 🎓 Key Learning Concepts

| Concept | Where You'll See It | Why It Matters |
|---------|-------------------|----------------|
| **Serialization** | `MemoryStore` — saving LangChain messages to SQLite | Real systems must persist data |
| **State propagation** | `known_entities` flowing through graph nodes | How context travels in multi-agent systems |
| **Context injection** | Supervisor prompt augmentation with entity/pref data | Making LLMs context-aware without fine-tuning |
| **Separation of concerns** | `memory.py` + `preferences.py` separate from `graph.py` | Good software design: each file has one job |
| **Stateful vs stateless** | Before (Phase 1) vs after (Phase 2) | Core architectural difference in agent design |

---

## ⚡ Quick Start for Phase 2

```bash
# 1. Create and switch to Phase 2 branch
git checkout -b claude/phase-2-ceArC

# 2. Start with Phase 2.1 (memory)
# Create src/confluence_mcp/agent/memory.py

# 3. Write tests first (TDD approach)
# Create tests/test_phase2.py with memory tests

# 4. Implement until tests pass
pytest tests/test_phase2.py -v

# 5. Move to Phase 2.2 (entity tracking), repeat

# 6. Move to Phase 2.3 (preferences), repeat

# 7. Verify nothing broke
pytest tests/ -v
```

---

## 💡 Design Decisions & Tradeoffs

| Decision | Why |
|---------|-----|
| **SQLite over vector DB** | Simple, no extra service needed, sufficient for conversation history. Vector DBs are for semantic search (Phase 8+). |
| **JSON file for preferences** | Human-readable, editable by hand, no DB overhead for small data |
| **`known_entities` in AgentState** | Entities need to flow through the graph in-session; memory.db is for between sessions |
| **Entity extraction in SearchAgent** | Search is the source of truth for page IDs — cleanest place to capture them |
| **No ML for preference learning** | Explicit user statements are more reliable than inference for v1 |

---

**Created**: 2026-02-20
**Status**: 📋 Plan Ready — Awaiting Phase 2 Start
**Branch**: `claude/phase-2-ceArC` (to be created)
