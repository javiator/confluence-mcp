from typing import Annotated, Literal, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
# Assuming sys.path is fixed by app.py or environment
from src.confluence_mcp.agent.client import MCPClient
from src.confluence_mcp.agent.llm import get_llm
import json

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def create_graph(mcp_client: MCPClient, provider: str = "openai", model: str = None):
    
    # 1. Convert MCP tools to format expected by LLM
    # We use the raw JSON schema from MCP
    mcp_tools = mcp_client.get_tools()
    
    formatted_tools = []
    for t in mcp_tools:
        formatted_tools.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.inputSchema
            }
        })

    # 2. Initialize LLM and bind tools
    llm = get_llm(provider, model)
    llm_with_tools = llm.bind_tools(formatted_tools)

    # 3. Define Nodes
    
    async def agent_node(state: AgentState):
        messages = state["messages"]
        
        # System Instruction
        system_instruction = """You are a helpful Confluence Assistant.
        You have access to MCP tools that work with Confluence:
        - search_confluence(query)
        - get_confluence_page(pageId)
        - create_confluence_page(spaceKey, parentId, title, body)
        - prepare_confluence_page_merge_update(pageId)
        - update_confluence_page_full(pageId, body)
        - get_confluence_children(pageId)

        General rules:
        - Treat Confluence as the single source of truth for pages.
        - When creating or updating pages, always work in Confluence storage format (XHTML-style HTML with <p>, <ul>, tables, and <ac:structured-macro> etc.).
        - Never assume you know the latest page content: if you are going to change an existing page, you must read it first using the appropriate tool.
        - Only pages labelled ai-generated or ai-managed are safe for full-page updates.

        Reading and searching:
        - When the user asks about existing documentation, decisions, specs, or runbooks:
            1. First call search_confluence(query) with a concise search phrase.
            2. Then call get_confluence_page(pageId) on the most relevant result(s) to summarise or quote from them.
        - When the user asks for "children" or "pages under X", ALWAYS use the `get_confluence_children` tool first. Do NOT rely on CQL search for hierarchy unless specifically asked.
        - Always clearly show the page title and URL when referencing a page.

        Creating new pages:
        - When the user asks you to create a new page:
            1. Clarify (or infer) the spaceKey, parentId, and title from context or from the user’s instructions.
            2. Draft the page body directly in storage format HTML.
            3. Call create_confluence_page(spaceKey, parentId, title, body) with the full storage-format body.
            4. Assume the server will automatically add an ai-generated label.

        Safe update flow (smart merge):
        - When the user wants to change an existing AI-generated page (improve it, add new sections, update details):
            1. Call prepare_confluence_page_merge_update(pageId) first.
            2. Use the returned textContent and storageContent as the current ground truth.
            3. Read the user’s requested changes and decide how to merge them:
                - Preserve any important existing information unless the user explicitly wants it removed.
                - Update numbers, facts, and examples where requested.
                - Add new sections where appropriate.
            4. Generate a new complete page body in storage-format HTML that:
                - Includes the merged content (old + new),
                - Is self-contained,
                - Is well structured (headings, lists, tables, macros as needed).
            5. Call update_confluence_page_full(pageId, body) with this final merged body.

        Overwriting without merge (use sparingly):
        - Only overwrite an entire page without considering old content if the user explicitly asks for a complete replacement and confirms that old content can be discarded.
        - In that case, you may skip the merge logic and:
            1. Optionally inspect the current page with prepare_confluence_page_merge_update(pageId) for context,
            2. Then construct a fresh storage-format body,
            3. And call update_confluence_page_full(pageId, body) to replace it entirely.

        Safety and correctness:
        - Never update a page that is not confirmed to be AI-managed (ai-generated / ai-managed); if the tools return an access error, explain that you cannot update that page.
        - Do not attempt to modify content you haven’t fetched in the current conversation.
        - When in doubt, propose changes in natural language or as a draft body, and let the user confirm before calling update tools.
        """
        
        # Prepend SystemMessage
        from langchain_core.messages import SystemMessage
        if not isinstance(messages[0], SystemMessage):
             messages = [SystemMessage(content=system_instruction)] + messages
        
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    async def tool_node(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {"messages": []}

        results = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            # Execute tool via MCP Client
            output = await mcp_client.call_tool(tool_name, tool_args)
            
            results.append(ToolMessage(
                tool_call_id=tool_id,
                name=tool_name,
                content=output
            ))
            
        return {"messages": results}

    # 4. Define Conditional Logic
    def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return "__end__"

    # 5. Build Graph
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    workflow.set_entry_point("agent")
    
    workflow.add_conditional_edges(
        "agent",
        should_continue,
    )
    
    workflow.add_edge("tools", "agent")

    return workflow.compile()
