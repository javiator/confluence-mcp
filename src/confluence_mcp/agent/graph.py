from typing import Annotated, Literal, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from confluence_mcp.agent.client import MCPClient
from confluence_mcp.agent.llm import get_llm

# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next: str          # supervisor routing target
    active_agent: str  # tracks which agent owns pending tool calls

# ── Tool groups ────────────────────────────────────────────────────────────────

SEARCH_TOOLS  = {"search_confluence", "get_confluence_page", "get_confluence_children"}
WRITER_TOOLS  = {"create_confluence_page", "prepare_confluence_page_merge_update",
                 "update_confluence_page_full"}
REVIEWER_TOOLS = {"get_confluence_page"}

# ── System prompts (concise = fewer tokens per call) ──────────────────────────

SUPERVISOR_PROMPT = """You route tasks to 3 Confluence agents. Reply with ONE word only:
- search  → find, read, or browse pages
- writer  → create or update pages
- reviewer → review/validate a page after writing
- end     → task is fully complete

Look at the full conversation. If an agent just finished and the task is done, reply: end."""

SEARCH_PROMPT = """You are a Confluence Search Specialist.
Use search_confluence, get_confluence_page, get_confluence_children to find and summarise information.
Always include page title and URL in your response."""

WRITER_PROMPT = """You are a Confluence Writer Specialist.
- To create: use create_confluence_page with Confluence storage format (XHTML).
- To update: call prepare_confluence_page_merge_update first, merge content, then update_confluence_page_full.
- Only update pages labelled ai-managed or ai-generated."""

REVIEWER_PROMPT = """You are a Confluence Content Reviewer.
Fetch the page with get_confluence_page, then give a concise review covering:
structure, clarity, completeness, and accuracy."""

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
        response = await llm.ainvoke(
            [SystemMessage(content=SUPERVISOR_PROMPT)] + state["messages"]
        )
        route = response.content.strip().lower().split()[0]
        if route not in {"search", "writer", "reviewer"}:
            route = "end"
        return {"next": route}

    # ── Agent node factory ─────────────────────────────────────────────────────

    def make_agent(agent_llm, system_prompt: str, agent_name: str):
        async def node(state: AgentState):
            msgs = state["messages"]
            if not isinstance(msgs[0], SystemMessage):
                msgs = [SystemMessage(content=system_prompt)] + msgs
            response = await agent_llm.ainvoke(msgs)
            return {"messages": [response], "active_agent": agent_name}
        return node

    # ── Shared tool executor ───────────────────────────────────────────────────

    async def tool_node(state: AgentState):
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {"messages": []}
        results = []
        for call in last.tool_calls:
            output = await mcp_client.call_tool(call["name"], call["args"])
            results.append(ToolMessage(
                tool_call_id=call["id"],
                name=call["name"],
                content=output,
            ))
        return {"messages": results}

    # ── Routing helpers ────────────────────────────────────────────────────────

    def supervisor_route(state: AgentState) -> str:
        return state["next"]

    def agent_route(state: AgentState) -> Literal["tools", "supervisor"]:
        last = state["messages"][-1]
        return "tools" if (isinstance(last, AIMessage) and last.tool_calls) else "supervisor"

    def tools_route(state: AgentState) -> str:
        return state["active_agent"]  # return to whichever agent called tools

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
        {"search": "search", "writer": "writer", "reviewer": "reviewer"})

    return workflow.compile()
