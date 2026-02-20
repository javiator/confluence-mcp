# Phase 1: Multi-Agent System with LangGraph

> **Goal**: Transform single-agent MCP server into a multi-agent system with specialized roles and quality gates

---

## 🏗️ Architecture

### Before (Phase 0)
```
User → Single Agent → All 6 Tools → Confluence
```
- One agent with massive 1500-char system prompt
- All 6 tools bound to every LLM call
- No quality review before publishing

### After (Phase 1.1)
```
User → Supervisor → [SearchAgent | WriterAgent | ReviewerAgent] → Tools → Confluence
                          ↑                                            ↓
                          └────────── Quality Gate ──────────────────┘
```
- 4 agents: Supervisor + 3 specialists
- 2-3 tools per agent (focused)
- Pre-publish review gate for all creates/updates

---

## 👥 The Four Agents

### 1. 🧭 Supervisor (Router)
**Role**: Routes tasks to the right specialist

**Prompt**: ~450 chars
- Classifies user intent → outputs ONE word: `search` | `writer` | `reviewer` | `end`
- Understands review approval cycle
- Routes based on context (pending drafts, approvals, revisions)

**Tools**: None (just routing logic)

---

### 2. 🔍 Search Agent
**Role**: Find, read, and browse Confluence pages

**Prompt**: ~410 chars
- Tool usage patterns
- Always include page title + URL in responses

**Tools**:
- `search_confluence(query)` - CQL-based search
- `get_confluence_page(pageId)` - Fetch full content
- `get_confluence_children(pageId)` - List child pages

**Use Cases**: "Find pages about X", "What's in page Y?", "Show me child pages"

---

### 3. ✍️ Writer Agent
**Role**: Create and update Confluence pages

**Prompt**: ~890 chars
- **Format**: Confluence storage format (XHTML)
- **Safety**: Only update ai-generated/ai-managed pages
- **Merge workflow**: Always read before updating
- **Review**: Tool calls are held for review before execution

**Tools**:
- `create_confluence_page(spaceKey, parentId, title, body)`
- `prepare_confluence_page_merge_update(pageId)` - Read before update
- `update_confluence_page_full(pageId, body)` - Replace entire page

**Use Cases**: "Create a page about X", "Update page Y to add Z"

---

### 4. 🔎 Reviewer Agent
**Role**: Quality gate before publishing + review existing pages

**Prompt**: ~680 chars
- **Dual mode**: Review drafts (pre-publish) OR existing pages (post-publish)
- **Criteria**: Structure, clarity, completeness, accuracy, format
- **Output**: "APPROVED: ..." or "NEEDS REVISION: ..."

**Tools**:
- `get_confluence_page(pageId)` - For post-publish reviews only

**Use Cases**:
- Pre-publish: Automatic quality check before WriterAgent publishes
- Post-publish: "Review the quality of page X"

---

## 🔄 Example Flows

### Flow 1: Create Page (Pre-Publish Review)
```
1. User: "Create a page titled 'Team Goals' in space TEAM"

2. Supervisor → WriterAgent

3. WriterAgent calls create_confluence_page(spaceKey="TEAM", title="Team Goals", body="<p>...</p>")

4. tool_node: "This is a PUBLISH tool → HOLD for review"
   → Stores in pending_tool_call, returns "[Draft held for review]"

5. Supervisor (sees pending_tool_call) → ReviewerAgent

6. ReviewerAgent: Analyzes draft parameters
   → "APPROVED: Well-structured page with clear headings and format"
   → Sets review_status = "approved"

7. Supervisor (sees approved) → WriterAgent

8. WriterAgent → tool_node

9. tool_node: "review_status == approved → EXECUTE the pending call"
   → Actually calls create_confluence_page() → page published ✅

10. Supervisor → END
```

---

### Flow 2: Search (No Review Needed)
```
1. User: "Find pages about project alpha"

2. Supervisor → SearchAgent

3. SearchAgent calls search_confluence(query="project alpha")

4. tool_node: "This is a SEARCH tool → EXECUTE immediately"
   → Returns search results

5. SearchAgent: Summarizes results with titles + URLs

6. Supervisor → END
```

---

### Flow 3: Update with Revision Loop
```
1. User: "Update page 12345 to add a new section"

2. Supervisor → WriterAgent

3. WriterAgent:
   a. Calls prepare_confluence_page_merge_update(12345) → gets current content
   b. Merges new section with existing content
   c. Calls update_confluence_page_full(12345, merged_body)

4. tool_node: "PUBLISH tool → HOLD for review"

5. Supervisor → ReviewerAgent

6. ReviewerAgent: "NEEDS REVISION: New section has formatting issues"
   → Sets review_status = "needs_revision"

7. Supervisor (sees needs_revision) → WriterAgent

8. WriterAgent: Fixes formatting, calls update_confluence_page_full again

9. tool_node: "PUBLISH tool → HOLD again"

10. Supervisor → ReviewerAgent

11. ReviewerAgent: "APPROVED: Formatting corrected"

12. Supervisor → WriterAgent → tool_node → EXECUTE → published ✅
```

---

### Flow 4: Review Existing Page
```
1. User: "Review the quality of page 12345"

2. Supervisor → ReviewerAgent

3. ReviewerAgent: Calls get_confluence_page(12345) → fetches content

4. ReviewerAgent: Analyzes and reports findings
   → "APPROVED: Page is well-structured with clear headings..."
   OR
   → "NEEDS REVISION: Missing key sections, unclear structure..."

5. Supervisor → END (or WriterAgent if user asks to fix)
```

---

## 🔑 Key Mechanisms

### State Schema
```python
class AgentState(TypedDict):
    messages: list[BaseMessage]        # Conversation history
    next: str                          # Supervisor routing target
    active_agent: str                  # Which agent owns pending tool calls
    pending_tool_call: Optional[dict]  # Held create/update calls
    review_status: Optional[str]       # "approved" | "needs_revision"
```

### Pre-Publish Review Gate
Located in `tool_node` (graph.py:175-224):

```python
if tool_name in PUBLISH_TOOLS:  # create_confluence_page, update_confluence_page_full
    if state.get("review_status") == "approved":
        # Execute the approved call
        output = await mcp_client.call_tool(tool_name, tool_args)
    else:
        # Hold for review
        pending = {"name": tool_name, "args": tool_args, "id": tool_id}
        return {"pending_tool_call": pending}
else:
    # Execute immediately (search tools, prepare_merge, etc.)
    output = await mcp_client.call_tool(tool_name, tool_args)
```

### Routing Logic
Located in `supervisor_node` (graph.py:123-139):

```python
# Supervisor adds context based on state
if state.get("pending_tool_call"):
    context = "Writer has drafted content, awaiting review"
elif state.get("review_status") == "approved":
    context = "Reviewer approved draft, ready to publish"
elif state.get("review_status") == "needs_revision":
    context = "Reviewer requested changes, writer should revise"

# LLM classifies intent and outputs: search | writer | reviewer | end
response = await llm.ainvoke([SystemMessage(SUPERVISOR_PROMPT + context)] + messages)
route = response.content.strip().lower().split()[0]
```

---

## 📊 Improvements Over Phase 0

| Metric | Phase 0 | Phase 1.1 | Improvement |
|--------|---------|-----------|-------------|
| **System prompt size** | 1500 chars (monolith) | 400-900 chars/agent | **-40 to -70%** |
| **Tools per call** | 6 (all tools) | 2-3 (focused) | **-50 to -70%** |
| **Quality gate** | ❌ None | ✅ Pre-publish review | **+Quality** |
| **Specialization** | ❌ One agent does all | ✅ 3 specialists | **+Clarity** |
| **UI visibility** | Basic tool logs | Agent step badges 🧭🔍✍️🔎 | **+UX** |

---

## 🧪 Tests

**13 tests, all passing** (`tests/test_phase1.py`):

1. ✅ Tool groups are disjoint (search vs writer)
2. ✅ Reviewer tools are subset of search
3. ✅ All 6 MCP tools are covered
4. ✅ Supervisor prompt has all routes
5. ✅ Agent prompts are concise (<900 chars)
6. ✅ AgentState has required keys
7. ✅ Publish tools defined correctly
8. ✅ Reviewer prompt has approval keywords
9. ✅ Writer prompt has critical rules
10. ✅ Supervisor understands review flow

---

## 🎯 What You Can Do Now

### Search & Browse
- "Find pages about project alpha"
- "What's in page 12345?"
- "Show me child pages under page 67890"

### Create Pages (with Pre-Publish Review)
- "Create a page titled 'Meeting Notes' in space TEAM"
- "Create a runbook for deployment in space DOCS under parent 12345"

### Update Pages (with Pre-Publish Review)
- "Update page 12345 to add a new section about security"
- "Fix the formatting in page 67890"

### Review Quality
- "Review the quality of page 12345"
- Automatic review before any create/update publishes

---

## 🔍 Under the Hood

### File Structure
```
src/confluence_mcp/agent/
├── graph.py        # Multi-agent graph, supervisor, routing, tool gate
├── app.py          # Chainlit UI with agent step badges
├── client.py       # MCP client (unchanged)
└── llm.py          # LLM factory (unchanged)

tests/
├── test_phase0.py  # 3 tests (environment, imports, MCP tools)
└── test_phase1.py  # 10 tests (agents, routing, review flow)
```

### Token Optimization Strategy
1. **Focused prompts**: Each agent only sees rules relevant to its role
2. **Fewer tools**: Each agent only has 2-3 tools bound (vs 6 for all)
3. **Supervisor efficiency**: Routing prompt is tiny, outputs 1 word
4. **No redundancy**: Critical rules are stated once per agent, not repeated

### Quality Strategy
1. **Essential context**: Format, safety, merge rules where needed
2. **Pre-publish gate**: All creates/updates reviewed before execution
3. **Clear criteria**: ReviewerAgent has explicit checklist
4. **Revision loop**: Failed reviews route back to WriterAgent to fix

---

## 📚 Next Steps

Phase 1 is **complete**. To continue learning:

1. **Test it live**: Run `chainlit run src/confluence_mcp/agent/app.py` and try the flows above
2. **Phase 2**: Add memory, context awareness, and intelligent routing
3. **Benchmarking** (optional): Compare token usage vs Phase 0 in real scenarios

---

**Created**: 2026-02-20
**Status**: ✅ Complete
**Tests**: 13/13 passing
**Branch**: `claude/phase-1-ceArC`
