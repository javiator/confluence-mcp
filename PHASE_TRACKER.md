# Multi-Agent Learning Journey - Phase Tracker

> Quick reference for Claude Code to understand where you are and what's next

---

## 🎯 Current Status

**Current Phase**: Phase 5 - Experiment: Google Vertex ⚪ Not Started
**Current Branch**: `claude/understand-project-setup-1suZ6`
**Started**: 2026-02-21
**Completed**: 2026-02-24
**Status**: 🟢 Phase 4 Complete - AgentCore + Chainlit integration stabilized.

---

## 📋 Quick Phase Summary

| Phase | Focus | Duration | Status | Branch | Notes |
|-------|-------|----------|--------|--------|-------|
| **Phase 0** | Foundation & Audit | 2-3 days | 🟢 Complete | `claude/phase-0-ceArC` | All 3 tests passing |
| **Phase 1** | First Multi-Agent (LangGraph) | 1 week | 🟢 Complete | `claude/phase-1-ceArC` | 13/13 tests passing |
| **Phase 2** | Intelligence & Memory | 1 day | 🟢 Complete | `claude/phase-2-ceArC` | 12/12 tests passing |
| **Phase 3** | Experiment: CrewAI | 1 day | 🟢 Complete | `claude/phase-3-ceArC` | Role-based agents working |
| **Phase 4** | Experiment: AWS Bedrock | 1 week | 🟢 Complete | `claude/understand-project-setup-1suZ6` | Native mas with AgentCore |
| **Phase 5** | Experiment: Google Vertex | 1 week | ⚪ Pending | `claude/phase-5-ceArC` | |
| **Phase 6** | Framework Decision | 2-3 days | ⚪ Pending | `claude/phase-6-ceArC` | |
| **Phase 7** | Production Build | 2 weeks | ⚪ Pending | `claude/phase-7-ceArC` | |
| **Phase 8** | Advanced Features | 2 weeks | ⚪ Pending | `claude/phase-8-ceArC` | |
| **Phase 9** | Polish & Documentation | 1 week | ⚪ Pending | `claude/phase-9-ceArC` | |

**Legend**: 🟢 Completed | 🟡 In Progress | 🔴 Blocked | ⚪ Not Started

---

## 📝 Current Phase Details

### Phase 0: Foundation & Audit — ✅ COMPLETE

All deliverables done. 3/3 tests passing. See `docs/PHASE0_NOTES.md` for full audit.

---

### Phase 1: First Multi-Agent (LangGraph)

**Objective**: Introduce multi-agent coordination with specialized agents

**Tasks**:
- [x] Create `SearchAgent` — search_confluence, get_confluence_page, get_confluence_children
- [x] Create `WriterAgent` — create/prepare_merge/update_full
- [x] Create `ReviewerAgent` — get_confluence_page + quality review prompt
- [x] Implement supervisor pattern for routing between agents
- [x] Add agent activity visualization to Chainlit UI (🔍/✍️/🔎 step badges)
- [x] **Phase 1.1 Enhancement**: Enhanced prompts with critical context (format, safety, merge rules)
- [x] **Phase 1.1 Enhancement**: Pre-publish review flow (WriterAgent → ReviewerAgent → approve/reject gate)
- [x] **Phase 1.1 Enhancement**: Post-publish review capability (explicit "review page X" requests)
- [x] **Phase 1.1 Enhancement**: Tool gate intercepts create/update calls for quality control
- [x] Write Phase 1 tests (`tests/test_phase1.py`) — 10 tests, all passing
- [ ] Benchmark multi-agent vs single agent performance (measure in real use)

**Estimated Time**: 1 week

**Key Deliverables**:
1. 3 specialized LangGraph agents with a supervisor
2. Agent routing logic (which agent handles what)
3. Updated Chainlit UI showing agent activity
4. Benchmarks comparing Phase 0 vs Phase 1 performance

**When to Consider Complete**:
- [x] Multi-agent workflow handles a full search → write → review cycle ✅
- [x] Chainlit shows which agent is active (🧭🔍✍️🔎 badges) ✅
- [x] Tests pass for all agents (13/13 passing) ✅
- [~] Performance measured vs baseline (deferred to real-world usage)

**Git Branching Strategy**:
- Pattern: `claude/phase-{N}-{SESSION_ID}`
- Current: `claude/phase-1-ceArC`
- Next: `claude/phase-2-ceArC` (use `./scripts/next-phase.sh`)
- See: `GIT_BRANCHING_STRATEGY.md` for details

---

### Phase 3: Experiment: CrewAI — ✅ COMPLETE

**Objective**: Rebuild functionality using CrewAI and compare with LangGraph.

**Tasks**:
- [x] Port Agents (Search, Writer, Reviewer) to CrewAI format
- [x] Implement dynamic tool wrappers for MCP (Pydantic v2 `BaseTool`)
- [x] Resolve cross-thread async deadlocks with `run_coroutine_threadsafe`
- [x] Implement real-time progress indicators via `step_callback`
- [x] Add conversation memory via history injection into Task descriptions
- [x] document framework comparison in `docs/frameworks/CREWAI_COMPARISON.md`

**Key Deliverables**:
1. CrewAI-powered Confluence Agents
2. High-quality Pydantic schema generation for dynamic tools
3. Thread-safe MCP integration bridge
4. Detailed Side-by-Side comparison with LangGraph

**When to Consider Complete**:
- [x] Agent completes full search → write → review cycle ✅
- [x] UI shows real-time progress steps ✅
- [x] Agents remember user context (name, history) ✅
- [x] Comparison document finalized ✅

---

### Phase 4: Experiment: AWS Bedrock 🟡 In Progress

**Objective**: Try managed service approach, understand cloud-native multi-agent

**Tasks**:
- [x] Set up AWS Bedrock Agents (Infrastructure as Code)
- [x] Create Lambda functions for tools (MCP to Lambda bridge)
- [ ] Deploy and test Bedrock Agent
- [ ] Compare with local frameworks (LangGraph, CrewAI)

**Key Deliverables**:
1. Deployed AWS Bedrock Agent
2. Lambda-based tool implementation
3. Cost analysis
4. Comparison document

**When to Consider Complete**:
- [x] Agent completes full search → write → review cycle via AWS Bedrock ✅
- [x] Lambda functions successfully bridge to MCP Server Logic ✅
- [x] Implement persistent session memory via payload-injected `sessionId` ✅
- [x] Optimize costs using Claude 3 Haiku and configurable model logic ✅

## 🎓 Learning Log

### Phase 0 Learnings
- ✅ **Project Structure**: Understood existing MCP server + Chainlit UI architecture
- ✅ **Environment Setup**: Successfully migrated to `uv` package manager
- ✅ **Git Strategy**: Implemented phase-based branching (claude/phase-N-SESSION_ID)
- ✅ **Documentation**: Created comprehensive phase guides and tracking
- ✅ **Testing**: Set up pytest framework with test structure
- 📝 **Current Capabilities**:
  - MCP server with Confluence integration
  - Chainlit-based UI for agent interaction
  - Basic search and retrieval working
  - Ready for multi-agent enhancement

### Phase 1 Learnings
- ✅ **Multi-Agent Design**: Supervisor + 3 specialists (Search, Writer, Reviewer) works well
- ✅ **LangGraph Routing**: Conditional edges based on state fields (`next`, `active_agent`, `pending_tool_call`)
- ✅ **Pre-Publish Review**: Tool gate pattern - intercept publish tools → hold → review → execute
- ✅ **Quality vs Tokens**: 400-900 char prompts balance context (quality) with efficiency (40-70% smaller)
- ✅ **Tool Specialization**: 2-3 tools per agent (vs 6 for all) reduces LLM context per call
- ✅ **State Management**: `pending_tool_call` + `review_status` enable approval workflows
- ✅ **UI Visibility**: Agent step badges (🧭🔍✍️🔎) make multi-agent flow transparent
- 📝 **Key Pattern**: tool_node acts as quality gate - checks `review_status` before executing PUBLISH_TOOLS
- 📝 **Dual-Mode Agents**: ReviewerAgent handles both pre-publish drafts AND post-publish reviews
- 📝 **Supervisor Context**: Adding state context to supervisor prompt improves routing accuracy

### Phase 2 Learnings
- ✅ **Conversation Persistence**: SQLite-backed memory enables session resumption across restarts
- ✅ **Entity Tracking**: Structured extraction of pages/spaces from tool results enables "it"/"that page" resolution
- ✅ **Coreference Resolution**: Simple rule-based patterns (it → last_page) solve 90% of cases
- ✅ **Chain of Thought**: Explicit reasoning logs make agent decisions transparent and debuggable
- ✅ **Confidence Scoring**: Rule-based routing (0.6-1.0) balances speed (no LLM call) with accuracy
- ✅ **Hybrid Context**: Full message history + entity summary provides safety + future optimization path
- 📝 **Key Pattern**: Entity extraction in tool_node captures structured data automatically from tool results
- 📝 **Serialization**: LangChain messages require careful JSON serialization (tool_calls, tool_call_id preservation)
- 📝 **State Explosion**: Each new feature adds fields to AgentState - need discipline to avoid bloat

### Phase 3 Learnings
- ✅ **Role Abstraction**: CrewAI's `Agent` role/goal/backstory makes prompting very intuitive (9/10 DX)
- ✅ **Pydantic Strictness**: `BaseTool` requires explicit `args_schema` derived from JSON schemas for dynamic tools
- ✅ **Threading Constraints**: CrewAI runs in separate threads - `asyncio.run_coroutine_threadsafe` is mandatory for MCP bridge
- ✅ **Task Statelessness**: Conversation history must be manually formatted and injected into task strings
- ✅ **UI Responsiveness**: `step_callback` is essential to prevent "black box" behavior in Chainlit
- 📝 **Key Pattern**: A Class Factory is the cleanest way to create CrewAI tools from dynamic MCP data
- 📝 **Ordering logic**: Sequential processes in CrewAI require careful UI message management to keep final results at the bottom

### Framework Comparison Notes
- **LangGraph**: ✅ Phase 1 Complete
  - **Pros**: Explicit state management, conditional routing, tool binding flexibility, good for complex workflows
  - **Cons**: More boilerplate (StateGraph, nodes, edges), steeper learning curve than simple chains
  - **Best for**: Multi-agent systems with approval gates, complex routing logic, state-dependent behavior
  - **Verdict so far**: Excellent control, suitable for production use
- **CrewAI**: ✅ Phase 3 Complete
  - **Pros**: Declarative role-playing, very low boilerplate for linear chains, intuitive task delegation
  - **Cons**: Debugging threading is hard, stateless tasks require manual memory management, less control than Graph
  - **Best for**: Content teams, research pipelines, autonomous sequential tasks
  - **Verdict so far**: Excellent for speed of development; LangGraph better for complex state/human-gates
- **AWS Bedrock**: ✅ Phase 4 Complete
  - **Pros**: Zero-infrastructure management (AgentCore handles the loop), native AWS security, extremely scalable, managed memory.
  - **Cons**: Debugging runtime crashes can be difficult (CloudWatch logs are the only view), rigid container environment requires redeploy for code changes.
  - **Best for**: Production enterprise applications, high-security environments, systems requiring long-term managed memory.
  - **Verdict**: The most robust and production-ready option yet.

- **Google Vertex**: [Phase 5 - To be explored]

---

## 🚧 Blockers & Questions

### Current Blockers
- None yet

### Questions for Next Session
1. [Add questions here]
2. [Ask Claude Code when you return]

---

## 💡 Ideas & Insights

### Things to Try
- [Add experimental ideas here]

### Improvements Discovered
- [Note improvements as you learn]

---

## 📊 Framework Decision Criteria (Fill as you experiment)

| Criteria | Weight | LangGraph | CrewAI | AWS Bedrock | Vertex AI |
|----------|--------|-----------|--------|-------------|-----------|
| **Ease of Learning** | High | ? | ? | ? | ? |
| **Flexibility** | High | ? | ? | ? | ? |
| **Production Ready** | High | ? | ? | ? | ? |
| **Cost** | Medium | ? | ? | ? | ? |
| **Maintenance** | Medium | ? | ? | ? | ? |
| **My Use Case Fit** | High | ? | ? | ? | ? |
| **TOTAL SCORE** | | 0 | 0 | 0 | 0 |

**Scoring**: 1-5 where 5 is best

---

## 🎯 Next Session Goals

When you come back, tell Claude Code:
- "I'm working on Phase [X]"
- "Help me with [specific task]"
- Or just: "Continue from where we left off"

---

**Last Updated**: 2026-02-20 (Phase 3 Complete)
**Next Review Date**: When starting Phase 4

**Phase 1 Summary**: See `docs/PHASE1_SUMMARY.md` for detailed architecture, flows, and examples.
