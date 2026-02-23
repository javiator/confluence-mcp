import os
import json
from typing import TypedDict, List, Union, Optional, Annotated
from langchain_aws import ChatBedrock
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from .client import MCPClient
from .llm import get_llm

# ── Configuration ──────────────────────────────────────────────────────────────

ALL_TOOLS = {
    "search_confluence", "get_confluence_page", "get_confluence_children",
    "execute_confluence_publish", "prepare_confluence_page_merge_update",
    "update_page_full", "append_to_page"
}

SYSTEM_PROMPT = """You are an expert Confluence Assistant.
Your primary job is to SEARCH for pages and PUBLISH new content.

CRITICAL OPERATIONAL RULES:
1. SILENT TOOL CALLS: DO NOT speak, acknowledge, or explain before calling a tool. If your next step is a tool call, respond ONLY with that tool call.
2. MANDATORY PAYLOAD: The argument for XHTML content is 'xhtml_payload' for creation and 'page_content_xhtml' for updates.
3. NEVER OMIT the payload. It is required for the tool to function.
4. You MUST provide the full, final XHTML in the first tool call. No placeholders.

STABILIZED WORKFLOW:
- SEARCH: search_confluence(query="...")
- CREATE: execute_confluence_publish(space_key="...", parent_id="...", title="...", xhtml_payload="...")
- UPDATE: update_page_full(page_id="...", page_content_xhtml="...")
- APPEND: append_to_page(page_id="...", page_content_xhtml="...")

FORMATTING RULES:
- Use strictly valid Confluence storage format (XHTML).
- DO NOT USE MARKDOWN within tool payloads (e.g., **, ##).
- DO NOT encode HTML entities (like &lt;, &gt;, &quot;, &amp;) manually. ALWAYS use literal characters (e.g., <, >, ", &).
- Double-check that your output is NOT escaped. If you see &lt;h1&gt;, it is WRONG. Use <h1>.
- CODE BLOCKS: Use <ac:structured-macro ac:name="code"> with <ac:plain-text-body><![CDATA[...]]> inside. ALWAYS close CDATA with ]]> IMMEDIATELY before </ac:plain-text-body>.
- TABLE OF CONTENTS: Use <ac:structured-macro ac:name="toc"/> at the top.

EXAMPLE: execute_confluence_publish(space_key="DS", parent_id="123", title="New Page", xhtml_payload="<h1>Hello</h1><ac:structured-macro ac:name=\\"code\\"><ac:plain-text-body><![CDATA[ls -la]]></ac:plain-text-body></ac:structured-macro>")"""

# ── State Definition ───────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    reasoning_trace: List[str]

# ── History Repair ─────────────────────────────────────────────────────────────

def repair_history_for_bedrock(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    Ensure the message history satisfies Bedrock's strict Converse API requirements:
    1. Alternating roles: user, assistant, user, assistant...
    2. ToolMessage (tool_result) MUST follow an AIMessage (tool_use).
    3. Consecutive same-role messages are merged or padded.
    """
    if not messages:
        return []

    # Filter out SystemMessages (Bedrock handles them separately)
    msgs = [m for m in messages if not isinstance(m, SystemMessage)]
    if not msgs:
        return []

    repaired = []
    
    # 1. Ensure the first message is a 'user' (HumanMessage)
    if isinstance(msgs[0], (AIMessage, ToolMessage)):
        repaired.append(HumanMessage(content="Beginning conversation."))
    
    for i, m in enumerate(msgs):
        if not repaired:
            repaired.append(m)
            continue

        prev = repaired[-1]
        
        # Rule: ToolMessage MUST follow an AIMessage with tool_calls
        if isinstance(m, ToolMessage):
            if not isinstance(prev, AIMessage) or not prev.tool_calls:
                # Ghost tool result detected! Prepend a fake AI call to satisfy Bedrock.
                repaired.append(AIMessage(content="", tool_calls=[{"name": m.name or "unknown", "args": {}, "id": m.tool_call_id}]))
            repaired.append(m)
            continue

        # Rule: HumanMessage (User) cannot follow another HumanMessage or ToolMessage (User) directly
        if isinstance(m, HumanMessage):
            if isinstance(prev, (HumanMessage, ToolMessage)):
                # Merge or pad
                prev.content = f"{prev.content}\n\n{m.content}"
                continue
            repaired.append(m)
            continue

        # Rule: AIMessage (Assistant) cannot follow another AIMessage directly
        if isinstance(m, AIMessage):
            if isinstance(prev, AIMessage):
                # Merge or pad
                prev.content = f"{prev.content}\n\n{m.content}"
                if m.tool_calls:
                    prev.tool_calls = (prev.tool_calls or []) + m.tool_calls
                continue
            repaired.append(m)
            continue

    return repaired

# ── Graph factory ──────────────────────────────────────────────────────────────

def create_bedrock_graph(mcp_client: MCPClient, model: str = None):
    llm = get_llm("bedrock", model)
    mcp_tools = {t.name: t for t in mcp_client.get_tools() if t.name in ALL_TOOLS}

    def lc_tools(names: set) -> list:
        return [
            {
                "type": "function",
                "function": {
                    "name": mcp_tools[n].name,
                    "description": mcp_tools[n].description,
                    "parameters": mcp_tools[n].inputSchema,
                }
            }
            for n in names if n in mcp_tools
        ]

    agent_llm = llm.bind_tools(lc_tools(ALL_TOOLS))

    async def agent_node(state: AgentState):
        msgs = state["messages"]
        reasoning_trace = state.get("reasoning_trace", []).copy()

        # Build repaired history for Bedrock
        repaired_history = repair_history_for_bedrock(msgs)
        llm_messages = [SystemMessage(content=SYSTEM_PROMPT)] + repaired_history

        reasoning_trace.append("🤖 Agent: Thinking and responding...")
        
        try:
            response = await agent_llm.ainvoke(llm_messages)
        except Exception as e:
            # Fallback if Bedrock still complains about history
            reasoning_trace.append(f"⚠️ History issue detected. Retrying with minimized context.")
            # Minimized context: System + Last Human + Current Turn
            minimized = [SystemMessage(content=SYSTEM_PROMPT)]
            last_human = next((m for m in reversed(repaired_history) if isinstance(m, HumanMessage)), None)
            if last_human:
                minimized.append(last_human)
            # Add any tool results that were part of the current turn
            if isinstance(repaired_history[-1], ToolMessage):
                 # Find the AI message that triggered it
                 for i in range(len(repaired_history)-1, -1, -1):
                    if isinstance(repaired_history[i], AIMessage) and repaired_history[i].tool_calls:
                        minimized.insert(1, repaired_history[i])
                        minimized.append(repaired_history[-1])
                        break
            response = await agent_llm.ainvoke(minimized)

        return {"messages": [response], "reasoning_trace": reasoning_trace}

    async def tool_node(state: AgentState):
        last = state["messages"][-1]
        results = []
        reasoning_trace = state.get("reasoning_trace", []).copy()
        
        for call in last.tool_calls:
            name, args, tid = call["name"], call["args"], call["id"]
            reasoning_trace.append(f"⚙️ Tool: {name}")
            try:
                output = await mcp_client.call_tool(name, args)
                output_str = json.dumps(output) if isinstance(output, (dict, list)) else str(output)
            except Exception as e:
                output_str = f"Error executing tool {name}: {str(e)}"
            
            results.append(ToolMessage(tool_call_id=tid, name=name, content=output_str))

        return {"messages": results, "reasoning_trace": reasoning_trace}

    def should_continue(state: AgentState):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()
