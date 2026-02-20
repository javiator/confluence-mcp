import os
from dotenv import load_dotenv
load_dotenv()

import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage
from confluence_mcp.agent.client import MCPClient
from confluence_mcp.agent.graph import create_graph

AGENT_LABELS = {
    "search":   "🔍 Search Agent",
    "writer":   "✍️  Writer Agent",
    "reviewer": "🔎 Reviewer Agent",
    "supervisor": "🧭 Supervisor",
}

# Global MCP Client removed to prevent shared state issues
# mcp_client = MCPClient()

# ...

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Search Confluence",
            message="Search for pages about 'project alpha' in space AR",
            icon="/public/search.svg",
        ),
        cl.Starter(
            label="Get Page Content",
            message="Get the content of page 12345",
            icon="/public/file.svg",
        ),
        cl.Starter(
            label="Create Page",
            message="Create a new page titled 'Meeting Notes' in space AR with some sample content",
            icon="/public/plus.svg",
        ),
    ]

@cl.on_chat_start
async def on_chat_start():
    # 1. Connect to MCP Server (Session Scoped)
    mcp_client = MCPClient()
    try:
        await mcp_client.connect()
        cl.user_session.set("mcp_client", mcp_client)
    except Exception as e:
        await cl.Message(content=f"Failed to connect to MCP Server: {e}").send()
        return

    # 2. Get User Settings (Model Selection)
    provider = os.environ.get("LLM_PROVIDER", "openai")
    model = os.environ.get("LLM_MODEL", "gpt-4o")
    
    # 3. Initialize Graph
    graph = create_graph(mcp_client, provider, model)
    cl.user_session.set("graph", graph)
    
    # Store provider/model info for later use (don't send message to avoid hiding starters)
    cl.user_session.set("llm_info", f"{provider}/{model}")

@cl.on_message
async def on_message(message: cl.Message):
    graph = cl.user_session.get("graph")
    
    if not graph:
        # Fallback: try to re-initialize if missing (e.g. after reload)
        provider = os.environ.get("LLM_PROVIDER", "openai")
        model = os.environ.get("LLM_MODEL", "gpt-4o")
        
        mcp_client = cl.user_session.get("mcp_client")
        if not mcp_client:
             mcp_client = MCPClient()
             try:
                await mcp_client.connect()
                cl.user_session.set("mcp_client", mcp_client)
             except Exception as e:
                await cl.Message(content=f"Error initializing agent: {e}").send()
                return

        try:
            graph = create_graph(mcp_client, provider, model)
            cl.user_session.set("graph", graph)
        except Exception as e:
            await cl.Message(content=f"Error initializing agent: {e}").send()
            return

    # Maintain conversation history in session
    history = cl.user_session.get("history", [])
    history.append(HumanMessage(content=message.content))
    
    inputs = {"messages": history}
    
    msg = cl.Message(content="")
    await msg.send()

    current_step = None   # active tool step
    agent_step = None     # active agent badge step

    try:
        async for event in graph.astream_events(inputs, version="v1"):
            kind = event["event"]
            node  = event.get("name", "")

            # Show which agent node just started
            if kind == "on_chain_start" and node in AGENT_LABELS:
                agent_step = cl.Step(name=AGENT_LABELS[node], type="run", parent_id=msg.id)
                agent_step.input = ""
                await agent_step.send()

            elif kind == "on_chain_end" and node in AGENT_LABELS and agent_step:
                await agent_step.update()
                agent_step = None

            elif kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    if isinstance(content, list):
                        parts = [b if isinstance(b, str) else b.get("text", "") for b in content]
                        content = "".join(parts)
                    if isinstance(content, str):
                        await msg.stream_token(content)

            elif kind == "on_tool_start":
                import json as _json
                tool_input = event["data"].get("input")
                if isinstance(tool_input, (dict, list)):
                    tool_input = _json.dumps(tool_input, indent=2)
                current_step = cl.Step(name=event["name"], type="tool", parent_id=msg.id)
                current_step.input = tool_input
                current_step.language = "json"
                await current_step.send()

            elif kind == "on_tool_end" and current_step:
                import json as _json
                tool_output = event["data"].get("output")
                if hasattr(tool_output, "content"):
                    raw = tool_output.content
                    if isinstance(raw, list):
                        current_step.output = "\n".join(
                            b if isinstance(b, str) else b.get("text", "") for b in raw
                        )
                    elif isinstance(raw, (dict, list)):
                        current_step.output = _json.dumps(raw, indent=2)
                        current_step.language = "json"
                    else:
                        current_step.output = str(raw)
                else:
                    current_step.output = str(tool_output)
                await current_step.update()
                current_step = None

    except Exception as e:
        await cl.Message(content=f"Error during execution: {str(e)}").send()
        return

    # Update history with the result
    # We need to fetch the final state to get the full history including tool messages
    # But astream_events doesn't return the final state directly.
    # For simplicity in this stateless-ish UI, we just append the final AIMessage
    # A better way is to use a persistent Checkpointer in LangGraph, but that's advanced.
    # We'll just rely on the graph returning the full list if we used ainvoke, 
    # but since we streamed, we need to reconstruct or just re-fetch.
    
    # For now, let's just append the final response to our local history
    history.append(AIMessage(content=msg.content))
    cl.user_session.set("history", history)
    
    await msg.update()

@cl.on_chat_end
async def on_chat_end():
    mcp_client = cl.user_session.get("mcp_client")
    if mcp_client:
        await mcp_client.close()
