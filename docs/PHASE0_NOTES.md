# Phase 0: Foundation & Audit - Notes

## Date Started: 2025-02-13

## Current State Audit

### Code Statistics
- **Total Lines of Code**: ~900 lines
- **Python Files**: 8 files
- **MCP Tools**: 6 tools
- **Framework**: LangGraph + FastMCP + Chainlit
- **Dependencies**: 222 packages (via uv)

### File Structure
```
src/confluence_mcp/
├── __init__.py          # Package initialization
├── __main__.py          # CLI entry point
├── server.py            # MCP server with 6 tools (~438 lines)
└── agent/
    ├── __init__.py
    ├── app.py           # Chainlit UI (~192 lines)
    ├── client.py        # MCP client (~50 lines)
    ├── graph.py         # LangGraph agent (~153 lines)
    └── llm.py           # LLM configuration (~67 lines)
```

### What Works Now
- ✅ MCP Server runs successfully (FastMCP)
- ✅ Can search Confluence (CQL-based with filters)
- ✅ Can create pages (access control: allowed spaces/parents)
- ✅ Can update pages (only AI-managed labels)
- ✅ Chainlit UI works (conversational + voice input)
- ✅ LangGraph agent works (single agent pattern)
- ✅ Multi-LLM support (OpenAI, Anthropic, Google)

### Current Architecture
```
┌──────────────────────────────────────────────┐
│            Chainlit UI                       │
│  - Conversational interface                  │
│  - Voice input (Google Gemini)               │
│  - Starter prompts                           │
│  - Tool execution visualization              │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│         LangGraph Agent (Single)             │
│  - System prompt with instructions           │
│  - Tool calling (MCP tools)                  │
│  - No specialization                         │
│  - No memory/state persistence               │
│  - No multi-agent coordination               │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│            MCP Client                        │
│  - Connects to MCP server via stdio          │
│  - Converts MCP tools to LLM format          │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│         MCP Server (FastMCP)                 │
│  Tools:                                      │
│  1. search_confluence()                      │
│  2. get_confluence_page()                    │
│  3. create_confluence_page()                 │
│  4. update_confluence_page_full()            │
│  5. prepare_confluence_page_merge_update()   │
│  6. get_confluence_children()                │
│                                              │
│  Access Control:                             │
│  - Allowed spaces (config.json)              │
│  - Allowed parents (config.json)             │
│  - AI-managed labels required for updates    │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│         Confluence REST API                  │
│  - CQL search                                │
│  - Content CRUD                              │
│  - Version management                        │
└──────────────────────────────────────────────┘
```

### Current Capabilities

#### 1. **Search** (search_confluence)
- **Technology**: CQL (Confluence Query Language)
- **Filtering**:
  - By allowed spaces (from config)
  - By allowed parent pages and descendants
  - Automatic ancestor filter application
- **Returns**: id, title, spaceKey, url, excerpt
- **Limit**: 50 results per query
- **Performance**: Fast (uses Confluence's indexed search)

#### 2. **Read** (get_confluence_page, get_confluence_children)
- **get_confluence_page**:
  - Retrieves by ID
  - Returns both textContent (plain) and storageContent (HTML)
  - No content size limits
  - Includes space info and URL
- **get_confluence_children**:
  - Gets direct children of a page
  - Validates parent page access
  - Returns: id, title, url
  - Limit: 50 children

#### 3. **Create** (create_confluence_page)
- **Access Control**:
  - Only in allowed spaces
  - Only under allowed parent pages
  - Validated before creation
- **Features**:
  - Automatically adds "ai-managed" label
  - Uses Confluence storage format (HTML)
  - Requires: spaceKey, parentId, title, body
- **Safety**: Restricted by config, labeled for tracking

#### 4. **Update** (update_confluence_page_full, prepare_confluence_page_merge_update)
- **Safety First**:
  - Only pages with "ai-managed" or "ai-generated" labels
  - Only in allowed spaces
  - Version management (auto-increment)
- **Smart Merge Support**:
  - prepare_confluence_page_merge_update(): fetches current content
  - Returns both text and storage format
  - Agent merges old + new content intelligently
- **Full Update**:
  - Overwrites entire page body
  - Validates labels and space before updating

#### 5. **Agent** (LangGraph)
- **Type**: Single general-purpose agent
- **System Prompt**: ~96 lines of instructions covering:
  - Tool usage guidelines
  - Reading and searching best practices
  - Creating new pages workflow
  - Safe update flow (smart merge)
  - Overwriting guidelines
  - Safety rules (AI-managed pages only)
- **Capabilities**:
  - Tool calling via LLM
  - Streaming responses
  - State management (messages list)
  - Conditional tool execution
- **Limitations**:
  - No specialization (does everything)
  - No memory persistence (per-session only)
  - No multi-agent coordination
  - No agent-to-agent communication
  - No parallel execution

### Pain Points / Areas for Improvement

1. **Single Agent Limitation**
   - One agent tries to do everything (search, write, review)
   - No specialization = jack of all trades, master of none
   - Can't leverage domain expertise

2. **No Memory/Learning**
   - Agent forgets between sessions
   - Can't learn from past actions
   - No shared knowledge base

3. **Sequential Only**
   - All operations happen one after another
   - Can't parallelize independent tasks
   - Slower for complex workflows

4. **No Coordination**
   - For complex tasks (e.g., "create comprehensive docs"), no way to:
     - Split work between specialized agents
     - Have agents collaborate
     - Review each other's work

5. **Limited Context**
   - System prompt is static
   - No dynamic context building
   - Can't adapt based on workspace patterns

6. **No Observability**
   - Can't see what agent is thinking
   - Hard to debug failures
   - No metrics on performance

7. **No Advanced Features**
   - No semantic search (keyword only via CQL)
   - No caching (repeated searches hit API)
   - No knowledge graph (relationships unknown)
   - No content analysis or health scoring

### Token Usage Baseline
(To be measured with actual usage)
- **Simple search**: ~500-1000 tokens (estimated)
- **Page creation**: ~3000-5000 tokens (estimated)
- **Agent workflow** (search + create): ~10000-15000 tokens (estimated)
- **System prompt**: ~1500 tokens

### Performance Baseline
(To be measured with actual usage)
- **Search latency**: ~1-2s (Confluence API)
- **Page retrieval**: ~1-2s per page
- **Page creation**: ~2-3s
- **Agent response time**: ~5-10s for simple operations
- **Complex workflow**: ~30-60s (sequential operations)

### Access Control Assessment
✅ **Strengths**:
- Space-level restrictions
- Parent page hierarchy enforcement
- AI-managed label requirement
- Configuration-based (flexible)

⚠️ **Considerations**:
- Config must be manually maintained
- No dynamic permission updates
- All-or-nothing per space

## Key Learnings

### What Works Well
1. **FastMCP Integration**: Clean, simple MCP server implementation
2. **Access Control**: Solid safety model with spaces + labels
3. **Storage Format**: Proper use of Confluence HTML format
4. **UI Experience**: Chainlit provides good conversational interface
5. **LangGraph Foundation**: Good starting point for multi-agent

### What Needs Improvement
1. **Agent Architecture**: Single agent is limiting
2. **No Persistence**: Memory resets each session
3. **Performance**: Sequential operations slow for complex tasks
4. **Observability**: Hard to debug and monitor
5. **Advanced Features**: Missing RAG, caching, knowledge graph

## Questions & Considerations

### Technical Questions
1. How will multi-agent coordination work?
2. Should we add persistent memory? Where to store?
3. Is RAG needed given Confluence has good search?
4. How to handle rate limits with more agents?

### Architecture Questions
1. Which framework will handle multi-agent best?
2. How to structure agent specializations?
3. Where does shared knowledge live?
4. How to measure agent performance?

### Business Questions
1. What workflows would benefit most from multi-agent?
2. Is the added complexity worth the benefits?
3. How to ensure quality doesn't decrease with automation?

## Next Steps

### Immediate (Phase 1)
- [ ] Create 3 specialized agents (Search, Writer, Reviewer)
- [ ] Implement supervisor pattern for routing
- [ ] Add agent visualization to Chainlit UI
- [ ] Test multi-agent workflow vs single agent

### Short-term (Phase 2-3)
- [ ] Add persistent memory
- [ ] Implement agent learning
- [ ] Experiment with CrewAI framework
- [ ] Benchmark performance differences

### Long-term (Phase 4+)
- [ ] Try all 6 frameworks
- [ ] Choose best framework for production
- [ ] Add advanced features (RAG, caching, knowledge graph)
- [ ] Deploy production system

## Evolution 0 Blog Post Outline

**Title**: "Evolution 0: Confluence MCP - Foundation & Baseline"

**Sections**:
1. Overview of current system
2. Architecture diagram
3. 6 MCP tools breakdown
4. Access control design
5. Single agent limitations
6. Why multi-agent is needed
7. Baseline metrics
8. What's next (Evolution 1)

**Key Points to Highlight**:
- Solid foundation with FastMCP + LangGraph
- Good safety model with access control
- Single agent limitation is the main bottleneck
- Ready for multi-agent enhancement

---

**Status**: Foundation audit complete ✅
**Next Phase**: Phase 1 - First Multi-Agent (LangGraph)
**Branch**: learning/phase-0
**Ready for blog post**: Yes
