from typing import Annotated, Literal, TypedDict, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from confluence_mcp.agent.client import MCPClient
from confluence_mcp.agent.llm import get_llm

# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next: str                          # supervisor routing target
    active_agent: str                  # tracks which agent owns pending tool calls
    pending_tool_call: Optional[dict]  # holds create/update calls for pre-publish review
    review_status: Optional[str]       # "approved" | "needs_revision" | None

# ── Tool groups ────────────────────────────────────────────────────────────────

SEARCH_TOOLS  = {"search_confluence", "get_confluence_page", "get_confluence_children"}
WRITER_TOOLS  = {"create_confluence_page", "prepare_confluence_page_merge_update",
                 "update_confluence_page_full"}
REVIEWER_TOOLS = {"get_confluence_page"}  # For post-publish review of existing pages

# Write operations that require pre-publish review
PUBLISH_TOOLS = {"create_confluence_page", "update_confluence_page_full"}

# ── Enhanced prompts (quality + critical context) ──────────────────────────────

SUPERVISOR_PROMPT = """You route tasks to 3 specialized Confluence agents. Reply with ONE word only:
- search   → find, read, or browse Confluence pages
- writer   → create new pages or update existing pages
- reviewer → review content quality (draft before publish OR existing published pages)
- end      → task is complete

Routing logic:
- User asks to find/read/browse → search
- User asks to create/update → writer
- User asks to review a specific page → reviewer
- After writer drafts content → automatically route to reviewer
- After reviewer approves → route back to writer to publish
- After reviewer requests changes → route back to writer to revise
- When task is fully complete → end

Look at the conversation history and any pending approvals in state."""

SEARCH_PROMPT = """You are a Confluence Search Specialist.

Tools at your disposal:
- search_confluence(query): CQL-based search across spaces
- get_confluence_page(pageId): Fetch full page content
- get_confluence_children(pageId): List child pages

Guidelines:
- Always provide page title and URL in your response
- Use get_confluence_children for hierarchy queries, not search_confluence
- Summarize findings clearly and concisely"""

WRITER_PROMPT = """You are a Confluence Writer Specialist.

Tools at your disposal:
- create_confluence_page(spaceKey, parentId, title, body): Create new pages
- prepare_confluence_page_merge_update(pageId): Fetch current content before updating
- update_confluence_page_full(pageId, body): Replace entire page body

Critical rules:
1. Format: Always use Confluence storage format (XHTML-style HTML: <p>, <ul>, <table>, <ac:structured-macro>)
2. Safety: Only update pages labeled ai-generated or ai-managed
3. Merge workflow for updates:
   - ALWAYS call prepare_confluence_page_merge_update(pageId) first
   - Merge new changes with existing content (preserve unless explicitly removing)
   - Then call update_confluence_page_full(pageId, merged_body)
4. Your tool calls will be reviewed before publishing

When creating/updating, draft high-quality content with proper structure, headings, and formatting."""

REVIEWER_PROMPT = """You are a Confluence Content Reviewer.

Your role:
- Review content BEFORE it's published to Confluence (pre-publish QA gate)
- Review existing published pages when explicitly requested

Review criteria:
1. Structure: Proper headings, logical flow, good formatting
2. Clarity: Clear, concise, well-written
3. Completeness: Covers the required topics thoroughly
4. Accuracy: Facts and details are correct
5. Format: Valid Confluence storage format (XHTML)

Process:
- If reviewing a draft (before publish): Check the pending content from the writer
- If reviewing existing page: Use get_confluence_page(pageId) to fetch and analyze

Output format:
- If APPROVED: Say "APPROVED: [brief summary of strengths]"
- If NEEDS REVISION: Say "NEEDS REVISION: [specific issues and suggestions]"

Be thorough but concise."""

# ── Graph factory ──────────────────────────────────────────────────────────────

def create_graph(mcp_client: MCPClient, provider: str = "openai", model: str = None):
    llm = get_llm(provider, model)

    # Build tool dicts once, keyed by name
    mcp_tools = {t.name: t for t in mcp_client.get_tools()}

    def lc_tools(names: set) -> list:
        return [
            {"type": "function", "function": {
                "name": mcp_tools[n].name,
                "description": mcp_tools[n].description,
                "parameters": mcp_tools[n].inputSchema,
            }}
            for n in names if n in mcp_tools
        ]

    search_llm   = llm.bind_tools(lc_tools(SEARCH_TOOLS))
    writer_llm   = llm.bind_tools(lc_tools(WRITER_TOOLS))
    reviewer_llm = llm.bind_tools(lc_tools(REVIEWER_TOOLS))

    # ── Supervisor ─────────────────────────────────────────────────────────────

    async def supervisor_node(state: AgentState):
        # Enhanced context: include pending state info
        context_msg = ""
        if state.get("pending_tool_call"):
            context_msg = "\n[Context: Writer has drafted content, awaiting review]"
        elif state.get("review_status") == "approved":
            context_msg = "\n[Context: Reviewer approved draft, ready to publish]"
        elif state.get("review_status") == "needs_revision":
            context_msg = "\n[Context: Reviewer requested changes, writer should revise]"

        response = await llm.ainvoke(
            [SystemMessage(content=SUPERVISOR_PROMPT + context_msg)] + state["messages"]
        )
        route = response.content.strip().lower().split()[0]
        if route not in {"search", "writer", "reviewer"}:
            route = "end"
        return {"next": route}

    # ── Agent node factory ─────────────────────────────────────────────────────

    def make_agent(agent_llm, system_prompt: str, agent_name: str):
        async def node(state: AgentState):
            msgs = state["messages"]

            # Add context for ReviewerAgent about what to review
            prompt = system_prompt
            if agent_name == "reviewer" and state.get("pending_tool_call"):
                pending = state["pending_tool_call"]
                prompt += f"\n\n[DRAFT TO REVIEW]\nTool: {pending['name']}\nParameters: {pending['args']}\n\nReview this draft before it's published."

            if not isinstance(msgs[0], SystemMessage):
                msgs = [SystemMessage(content=prompt)] + msgs
            else:
                # Replace first system message with our enhanced prompt
                msgs = [SystemMessage(content=prompt)] + msgs[1:]

            response = await agent_llm.ainvoke(msgs)

            # Extract review status from ReviewerAgent response
            updates = {"messages": [response], "active_agent": agent_name}
            if agent_name == "reviewer":
                content = response.content.lower()
                if "approved" in content and "needs revision" not in content:
                    updates["review_status"] = "approved"
                elif "needs revision" in content or "needs_revision" in content:
                    updates["review_status"] = "needs_revision"

            return updates
        return node

    # ── Tool executor with pre-publish review gate ─────────────────────────────

    async def tool_node(state: AgentState):
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {"messages": []}

        results = []
        pending = None

        for call in last.tool_calls:
            tool_name = call["name"]
            tool_args = call["args"]
            tool_id = call["id"]

            # Pre-publish review gate: hold create/update calls for review
            if tool_name in PUBLISH_TOOLS:
                if state.get("review_status") == "approved":
                    # Reviewer approved: execute the pending call
                    output = await mcp_client.call_tool(tool_name, tool_args)
                    results.append(ToolMessage(
                        tool_call_id=tool_id,
                        name=tool_name,
                        content=output,
                    ))
                else:
                    # Hold for review
                    pending = {"name": tool_name, "args": tool_args, "id": tool_id}
                    # Don't execute yet - store in state
                    results.append(ToolMessage(
                        tool_call_id=tool_id,
                        name=tool_name,
                        content="[Draft held for review - not yet published]",
                    ))
            else:
                # Execute immediately (search tools, prepare_merge, etc.)
                output = await mcp_client.call_tool(tool_name, tool_args)
                results.append(ToolMessage(
                    tool_call_id=tool_id,
                    name=tool_name,
                    content=output,
                ))

        updates = {"messages": results}
        if pending:
            updates["pending_tool_call"] = pending
        elif state.get("review_status") == "approved":
            # Clear state after successful publish
            updates["pending_tool_call"] = None
            updates["review_status"] = None

        return updates

    # ── Routing helpers ────────────────────────────────────────────────────────

    def supervisor_route(state: AgentState) -> str:
        return state["next"]

    def agent_route(state: AgentState) -> Literal["tools", "supervisor"]:
        last = state["messages"][-1]
        return "tools" if (isinstance(last, AIMessage) and last.tool_calls) else "supervisor"

    def tools_route(state: AgentState) -> str:
        # If we just held a tool for review, route to supervisor (who will route to reviewer)
        if state.get("pending_tool_call") and not state.get("review_status"):
            return "supervisor"
        # Otherwise return to the agent that called the tools
        return state["active_agent"]

    # ── Build graph ────────────────────────────────────────────────────────────

    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("search",     make_agent(search_llm,   SEARCH_PROMPT,   "search"))
    workflow.add_node("writer",     make_agent(writer_llm,   WRITER_PROMPT,   "writer"))
    workflow.add_node("reviewer",   make_agent(reviewer_llm, REVIEWER_PROMPT, "reviewer"))
    workflow.add_node("tools",      tool_node)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges("supervisor", supervisor_route,
        {"search": "search", "writer": "writer", "reviewer": "reviewer", "end": END})

    for agent in ("search", "writer", "reviewer"):
        workflow.add_conditional_edges(agent, agent_route,
            {"tools": "tools", "supervisor": "supervisor"})

    workflow.add_conditional_edges("tools", tools_route,
        {"search": "search", "writer": "writer", "reviewer": "reviewer", "supervisor": "supervisor"})

    return workflow.compile()
