from typing import Annotated, Literal, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from src.confluence_mcp.agent.client import MCPClient
from src.confluence_mcp.agent.llm import get_llm
import json

class AgentState(TypedDict):
    messages: list[BaseMessage]

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
