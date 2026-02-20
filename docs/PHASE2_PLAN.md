# Phase 2: Intelligence & Memory — Comprehensive Plan

> **Vision**: Transform stateless agents into intelligent assistants with memory, reasoning, and adaptive behavior

**Branch**: `claude/phase-2-ceArC`
**Estimated Duration**: 1 week (MVP), extensible beyond
**Prerequisite**: Phase 1 Complete ✅

---

## 🎯 What "Intelligence & Memory" Really Means

This isn't just about saving conversation history. It's about creating agents that:

1. **Remember** context across conversations
2. **Understand** implicit references and relationships
3. **Learn** from interactions and feedback
4. **Reason** through multi-step problems
5. **Adapt** their behavior based on experience
6. **Self-correct** when they make mistakes
7. **Explain** their thinking process

---

## 🧠 The Full Vision: Memory Systems

### 1. **Conversational Memory** (Short-term)
What the agent remembers **within** a session.

| Type | What It Stores | Example |
|------|---------------|---------|
| **Working Memory** | Current task context, active entities | "We're updating the deployment runbook (ID: 12345)" |
| **Turn-by-turn History** | Message sequence in current conversation | All `messages` in AgentState |
| **Tool Call History** | What tools were called and their results | "Just searched for 'API docs' and found 3 pages" |

### 2. **Episodic Memory** (Long-term)
What the agent remembers **between** sessions — specific events.

| Type | What It Stores | Example |
|------|---------------|---------|
| **Session History** | Past conversations with timestamps | "Last Tuesday you updated the API documentation page" |
| **Action Log** | Pages created/updated by user | "You've worked on 15 pages in the ENG space this month" |
| **Error History** | What went wrong in the past | "Last time we tried updating page X, it failed due to permissions" |

### 3. **Semantic Memory** (Long-term)
What the agent **knows** — learned facts and patterns.

| Type | What It Stores | Example |
|------|---------------|---------|
| **Space Knowledge** | What each space is for | "ENG = internal engineering docs, MKT = marketing content" |
| **Page Relationships** | Hierarchies and links | "The API docs page has 5 child pages about different endpoints" |
| **User Patterns** | Behavioral patterns | "User typically creates pages under parent 12345 in ENG space" |
| **Tool Effectiveness** | Which tools work best when | "search_confluence works better with CQL queries, not natural language" |

### 4. **Procedural Memory** (Long-term)
What the agent **knows how to do** — learned skills.

| Type | What It Stores | Example |
|------|---------------|---------|
| **Successful Workflows** | Multi-step patterns that worked | "When creating runbooks: 1) search for template, 2) copy structure, 3) customize" |
| **Error Recovery** | How to fix common failures | "If search returns 0 results, try broader query or search in parent space" |

---

## 🎓 The Full Vision: Intelligence Systems

### 1. **Context Understanding**

| Capability | What It Does | Example |
|-----------|-------------|---------|
| **Entity Resolution** | Resolve "it", "that page", "there" to actual IDs | "Update it" → "Update page 12345" |
| **Coreference Resolution** | Track what pronouns refer to | "The runbook needs updating. It's missing steps" → "it" = runbook |
| **Temporal Reasoning** | Understand "yesterday", "last week", "the most recent one" | "Show me the page we worked on yesterday" |
| **Spatial Reasoning** | Understand hierarchy and containment | "Create it under the same parent" |

### 2. **Advanced Reasoning**

| Capability | What It Does | Example |
|-----------|-------------|---------|
| **Chain of Thought (CoT)** | Step-by-step reasoning made visible | "To update the page, I need to: 1) fetch current content, 2) merge changes, 3) review" |
| **Multi-step Planning** | Break complex tasks into subtasks | "To create a full runbook: create main page, add sections, create child pages for each step" |
| **Causal Reasoning** | Understand cause and effect | "That update failed because the page isn't labeled ai-managed" |
| **Counterfactual Reasoning** | Consider alternatives | "If I had searched in the parent space first, I would have found it faster" |

### 3. **Self-Awareness & Meta-Cognition**

| Capability | What It Does | Example |
|-----------|-------------|---------|
| **Confidence Scoring** | Express uncertainty | "I'm 80% confident this is the right page, but there's another similar one" |
| **Self-Reflection** | Evaluate own performance | "That summary was too verbose. The user prefers concise answers." |
| **Clarification** | Ask questions when uncertain | "You said 'update the docs' — do you mean the API docs or deployment docs?" |
| **Explain Reasoning** | Show why a decision was made | "I routed to SearchAgent because you used the word 'find'" |

### 4. **Adaptive Behavior**

| Capability | What It Does | Example |
|-----------|-------------|---------|
| **Feedback Learning** | Adjust based on corrections | User: "Too long" → Next summary is shorter |
| **Preference Inference** | Learn implicit preferences | "User always creates pages in ENG space → default to ENG" |
| **Error Recovery** | Try alternatives when blocked | "Search failed → try broader query → try parent space → ask user" |
| **Tool Selection Optimization** | Learn which tools work best | "For hierarchy queries, get_confluence_children works better than search_confluence" |

### 5. **Proactive Intelligence**

| Capability | What It Does | Example |
|-----------|-------------|---------|
| **Anticipate Needs** | Suggest next steps | "You created a runbook. Would you like me to create child pages for each step?" |
| **Detect Patterns** | Notice repeated tasks | "You've updated this page 3 times this week. Should I watch it for changes?" |
| **Anomaly Detection** | Flag unusual situations | "This page hasn't been updated in 6 months but you usually update it monthly" |

---

## 📊 Priority Tiers: What to Build When

### **P0 (MVP — Week 1)** — Core Memory & Context

| Feature | Component | Why MVP |
|---------|-----------|---------|
| ✅ Conversation persistence | SQLite MemoryStore | Can't be intelligent without memory |
| ✅ Entity tracking (pages, spaces) | `known_entities` in AgentState | Solves "it"/"that page" problem immediately |
| ✅ Coreference resolution | Entity context injection | Enables natural conversation |
| ✅ Session resume | Chainlit UI + DB integration | User-facing value, easy to demo |

### **P1 (Should Have — Week 2)** — Intelligent Context

| Feature | Component | Why Important |
|---------|-----------|--------------|
| 🔲 User preferences | JSON preference store | Personalization, learned behavior |
| 🔲 Chain of Thought | Reasoning trace in state | Transparency, debuggability |
| 🔲 Confidence scoring | Supervisor confidence field | Better UX for ambiguous cases |
| 🔲 Clarification flow | New `clarification` agent/node | Handle ambiguity gracefully |
| 🔲 Tool call history tracking | `tool_history` in state | Learn what works/fails |

### **P2 (Nice to Have — Future Phases)** — Advanced Intelligence

| Feature | Component | When to Build |
|---------|-----------|--------------|
| 🔲 Semantic search over history | Vector embeddings (ChromaDB) | Phase 8 (Advanced Features) |
| 🔲 Multi-step planning | Task decomposition layer | Phase 7 (Production Build) |
| 🔲 Feedback learning | Reinforcement from corrections | Phase 8 |
| 🔲 Proactive suggestions | Anticipation engine | Phase 8 |
| 🔲 Space/page knowledge graph | Neo4j or in-memory graph | Phase 8 |

---

## 🏗️ Phase 2 Implementation Plan (1 Week MVP)

### **Day 1-2: Conversation Memory (P0)**

**Files**:
- `src/confluence_mcp/agent/memory.py` — SQLite-backed storage
- `src/confluence_mcp/agent/app.py` — Session management

**New AgentState fields**:
```python
class AgentState(TypedDict):
    # ... existing ...
    session_id: str                    # Unique conversation ID
    session_metadata: dict             # Created timestamp, user info
```

**Features**:
- [ ] Create `MemoryStore` class with save/load/list/delete
- [ ] Serialize LangChain messages to JSON (handle AIMessage, ToolMessage, etc.)
- [ ] Store in SQLite: `sessions` table (id, messages_json, created_at, updated_at)
- [ ] Integrate with Chainlit: load on start, save on message
- [ ] UI: show "Resuming from [date]" banner

**Tests**: 4 tests (save/load round-trip, empty session, list, delete)

---

### **Day 3-4: Entity Tracking & Resolution (P0)**

**Files**:
- `src/confluence_mcp/agent/graph.py` — State updates, context injection
- `src/confluence_mcp/agent/entities.py` (NEW) — Entity extraction utilities

**New AgentState fields**:
```python
class AgentState(TypedDict):
    # ... existing ...
    known_entities: dict  # {"pages": [...], "spaces": [...], "last_page": {...}, "last_space": "..."}
```

**Entity structure**:
```python
{
    "pages": [
        {"id": "12345", "title": "API Docs", "space": "ENG", "url": "...", "last_mentioned": timestamp},
        {"id": "67890", "title": "Deploy Guide", "space": "OPS", "url": "...", "last_mentioned": timestamp}
    ],
    "spaces": ["ENG", "OPS", "MKT"],
    "last_page": {"id": "12345", "title": "API Docs", "space": "ENG"},
    "last_space": "ENG"
}
```

**Features**:
- [ ] Extract entities from tool call results (SearchAgent, WriterAgent)
- [ ] Update `known_entities` after every search/fetch/create/update
- [ ] Inject entity context into Supervisor prompt
- [ ] Inject entity context into WriterAgent prompt
- [ ] Handle recency (keep 10 most recent pages, sorted by `last_mentioned`)
- [ ] Coreference: "it" → `last_page`, "that space" → `last_space`, "the page" → `last_page`

**Tests**: 5 tests (entity extraction, context injection, recency, coreference resolution, structure validation)

---

### **Day 5-6: Chain of Thought + Confidence (P1)**

**Files**:
- `src/confluence_mcp/agent/graph.py` — Add reasoning trace + confidence

**New AgentState fields**:
```python
class AgentState(TypedDict):
    # ... existing ...
    reasoning_trace: list[str]         # ["Step 1: Search for page", "Step 2: Found 3 results", ...]
    supervisor_confidence: float       # 0.0 - 1.0 confidence in routing decision
```

**Features**:
- [ ] Supervisor logs reasoning before routing ("User said 'find' → route to search")
- [ ] Each agent logs reasoning steps as they work
- [ ] Supervisor outputs confidence score with routing decision
- [ ] If confidence < 0.6 → route to clarification agent (future) OR ask user
- [ ] Chainlit UI: show reasoning trace in expandable details

**Tests**: 3 tests (reasoning trace populated, confidence in valid range, low confidence triggers clarification)

---

### **Day 7: User Preferences + Polish (P1)**

**Files**:
- `src/confluence_mcp/agent/preferences.py` (NEW) — JSON preference store

**Preference structure**:
```json
{
  "preferred_space": "ENG",
  "preferred_parent_page": "12345",
  "format_style": "concise",  // "concise" | "detailed"
  "tone": "technical",         // "technical" | "friendly" | "formal"
  "auto_review": true          // always review before publish
}
```

**Features**:
- [ ] `UserPreferences` class: load/save/update
- [ ] Explicit preference capture: "always use ENG space" → update preferences
- [ ] Implicit preference inference: if user creates 5 pages in ENG, suggest making it default
- [ ] Inject preferences into all agent prompts as context
- [ ] UI: `/prefs` command to view/edit preferences

**Tests**: 3 tests (load defaults, save/load, context injection)

**Polish**:
- [ ] Update all Phase 1 tests to pass with new state fields
- [ ] Write comprehensive `docs/PHASE2_SUMMARY.md`
- [ ] Update `PHASE_TRACKER.md`

---

## 🗂️ Complete File Structure (Phase 2)

```
src/confluence_mcp/agent/
├── graph.py          # AgentState with new fields, context injection
├── app.py            # Session management, memory integration
├── memory.py         # NEW: SQLite MemoryStore
├── entities.py       # NEW: Entity extraction and resolution utilities
├── preferences.py    # NEW: JSON-backed UserPreferences
├── client.py         # Unchanged
└── llm.py            # Unchanged

tests/
├── test_phase0.py    # 3 tests (unchanged)
├── test_phase1.py    # 16 tests (updated for new state fields)
├── test_phase2.py    # NEW: 15 tests (memory, entities, CoT, preferences)

~/.confluence_mcp/    # User data directory
├── memory.db         # SQLite: sessions table
└── preferences.json  # User preferences

docs/
├── PHASE0_NOTES.md
├── PHASE1_SUMMARY.md
├── PHASE2_PLAN.md    # This file
└── PHASE2_SUMMARY.md # Created at end of Phase 2
```

---

## 🧪 Test Plan (15 tests total)

### Memory Tests (4)
1. `test_memory_store_save_and_load` — Round-trip serialization
2. `test_memory_store_empty_session` — Non-existent session returns []
3. `test_memory_store_list_sessions` — Metadata correct
4. `test_memory_session_resume_in_app` — Integration test with Chainlit

### Entity Tests (5)
5. `test_entity_extraction_from_search` — SearchAgent extracts page entities
6. `test_entity_context_injection_supervisor` — Supervisor sees entity context
7. `test_entity_recency_ordering` — Most recent entities kept
8. `test_coreference_resolution` — "it" resolves to last_page
9. `test_known_entities_structure` — Schema validation

### Reasoning Tests (3)
10. `test_reasoning_trace_populated` — Supervisor logs reasoning
11. `test_confidence_score_valid_range` — Confidence between 0-1
12. `test_low_confidence_triggers_clarification` — <0.6 → ask user

### Preferences Tests (3)
13. `test_preferences_load_defaults` — Empty file → defaults
14. `test_preferences_save_and_load` — Round-trip
15. `test_preferences_injected_into_prompts` — Context includes prefs

---

## 📊 Success Criteria

| Capability | How to Verify | Priority |
|-----------|--------------|----------|
| **Conversation persists** | Stop app, restart, history loads | P0 ✅ |
| **"Update it" resolves** | Search page → say "update it" → works without clarification | P0 ✅ |
| **Entity tracking works** | Mention 3 pages, then say "the first one" → resolves correctly | P0 ✅ |
| **Reasoning visible** | Chainlit shows "Step 1: ..., Step 2: ..." | P1 |
| **Confidence shown** | Supervisor shows "(80% confident)" when routing | P1 |
| **Preferences persist** | Set pref, restart app, pref still active | P1 |
| **All 31 tests pass** | `pytest tests/ -v` (Phase 0: 3, Phase 1: 16, Phase 2: 15) | P0 ✅ |

---

## 🎓 Learning Outcomes

By the end of Phase 2, you'll understand:

| Concept | What You'll Learn | Where |
|---------|------------------|-------|
| **Serialization** | Converting Python objects ↔ JSON for storage | `memory.py` |
| **State management** | How context flows through a stateful graph | `AgentState` evolution |
| **Entity resolution** | NLP technique for pronoun/reference resolution | `entities.py` |
| **Persistence patterns** | SQLite for structured data, JSON for config | `memory.py`, `preferences.py` |
| **Context injection** | Augmenting LLM prompts with dynamic data | Supervisor/agent prompts |
| **Chain of Thought** | Making LLM reasoning explicit and traceable | `reasoning_trace` |
| **Confidence calibration** | How to express and use uncertainty | `supervisor_confidence` |
| **Personalization** | Adapting system behavior to user preferences | `preferences.py` |

---

## 🚀 Beyond Phase 2: Future Intelligence Features

These are **not in scope** for Phase 2 but are the natural next steps:

### **Phase 8: Advanced Intelligence**
- **Semantic memory search**: Vector embeddings (ChromaDB/Pinecone) for "find conversations about deployments"
- **Multi-step planning**: Decompose "create a complete runbook" into 10 subtasks
- **Feedback learning**: "That was too long" → adjust `format_style` preference automatically
- **Tool effectiveness learning**: Track which tools succeed/fail, optimize selection
- **Proactive suggestions**: "You usually create child pages after runbooks. Want me to do that?"
- **Knowledge graph**: Neo4j graph of spaces, pages, relationships for complex queries

### **Phase 9: Meta-Learning**
- **Self-improvement**: Agent analyzes own performance and proposes workflow improvements
- **Transfer learning**: Apply patterns from one space to another
- **Collaborative learning**: Multiple users' patterns aggregated (with privacy)

---

## 💡 Design Philosophy

### **Start Simple, Grow Smart**

1. **Week 1 (Phase 2 MVP)**: Basic memory + entity tracking
   - Solves 80% of UX problems
   - Minimal complexity
   - Easy to test and debug

2. **Week 4+ (Phase 8)**: Advanced intelligence
   - Vector search, planning, learning
   - Builds on solid foundation
   - Each feature adds incremental value

### **Explicit Over Implicit (For Now)**

- **Preferences**: Explicit capture ("always use ENG") before implicit inference
- **Coreference**: Simple recency rules ("it" = last_page) before complex NLP
- **Confidence**: Rule-based scoring before ML calibration

**Why**: Simpler systems are easier to debug, explain, and trust. Add complexity when simple solutions fail.

### **Visible Intelligence**

Every intelligence feature should have **UI visibility**:
- Reasoning trace → expandable log in Chainlit
- Confidence → shown as percentage
- Entity resolution → "Resolved 'it' → API Docs (12345)"
- Preferences → `/prefs` command to view

**Why**: Users trust systems they can understand and control.

---

## 🔗 Integration Points

### **With Phase 1**
- Entity tracking enhances Supervisor routing (more context = better decisions)
- Memory provides history for ReviewerAgent ("you updated this page yesterday")
- Preferences reduce back-and-forth (default space/parent already known)

### **With Phase 3+ (Future)**
- CrewAI/Bedrock/Vertex: All frameworks benefit from memory/entity tracking
- Comparison: Does multi-agent framework X handle state better than LangGraph?

### **With Phase 7 (Production)**
- Memory DB scales to handle thousands of sessions
- Preferences become team-shared (not just per-user)
- Entity graph persists across users (shared knowledge base)

---

## ⚙️ Implementation Notes

### **AgentState Evolution**

```python
# Phase 1 (before):
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next: str
    active_agent: str
    pending_tool_call: Optional[dict]
    review_status: Optional[str]
    revision_count: int

# Phase 2 (after):
class AgentState(TypedDict):
    # Phase 1 fields (unchanged)
    messages: Annotated[list[BaseMessage], add_messages]
    next: str
    active_agent: str
    pending_tool_call: Optional[dict]
    review_status: Optional[str]
    revision_count: int

    # Phase 2 additions
    session_id: str                    # P0: Conversation persistence
    session_metadata: dict             # P0: Created/updated timestamps
    known_entities: dict               # P0: Pages, spaces, last_page, last_space
    reasoning_trace: list[str]         # P1: Step-by-step reasoning log
    supervisor_confidence: float       # P1: Routing confidence 0.0-1.0
    tool_history: list[dict]           # P1: Log of tool calls + results (for learning)
```

### **Backward Compatibility**

All new fields have defaults so Phase 1 code continues to work:
```python
session_id: str = ""               # Empty string if not set
known_entities: dict = {}          # Empty dict if not set
reasoning_trace: list[str] = []    # Empty list if not set
```

---

**Created**: 2026-02-20
**Revised**: 2026-02-20 (Comprehensive Vision)
**Status**: 📋 Plan Ready — P0 MVP defined, P1/P2 roadmap clear
**Branch**: `claude/phase-2-ceArC` (to be created)
