import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

import chainlit as cl
import json
from langchain_core.messages import HumanMessage, AIMessage
from src.confluence_mcp.agent.client import MCPClient
from src.confluence_mcp.agent.graph import create_graph

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
    
    # We will track the current tool step to update it
    current_step = None
    
    try:
        async for event in graph.astream_events(inputs, version="v1"):
            kind = event["event"]
            
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    # Ensure content is a string (it might be a list for multimodal models)
                    if isinstance(content, list):
                        # Extract text from list of blocks if possible
                        text_parts = []
                        for block in content:
                            if isinstance(block, str):
                                text_parts.append(block)
                            elif isinstance(block, dict) and "text" in block:
                                text_parts.append(block["text"])
                        content = "".join(text_parts)
                    
                    if isinstance(content, str):
                        await msg.stream_token(content)
                    
            elif kind == "on_tool_start":
                # Create a new step for the tool
                tool_name = event["name"]
                tool_input = event["data"].get("input")
                
                # Format input as JSON for better readability
                if isinstance(tool_input, (dict, list)):
                    import json
                    tool_input = json.dumps(tool_input, indent=2)
                
                current_step = cl.Step(
                    name=tool_name,
                    type="tool",
                    parent_id=msg.id, # Nest step under the main message
                )
                current_step.input = tool_input
                current_step.language = "json"
                await current_step.send()
                
            elif kind == "on_tool_end":
                if current_step:
                    tool_output = event["data"].get("output")
                    # If output is a ToolMessage, extract content
                    if hasattr(tool_output, "content"):
                        content = tool_output.content
                        if isinstance(content, list):
                             # Handle list content (e.g. from MCP tools returning multiple blocks)
                             text_parts = []
                             for block in content:
                                 if isinstance(block, str):
                                     text_parts.append(block)
                                 elif isinstance(block, dict) and "text" in block:
                                     text_parts.append(block["text"])
                             current_step.output = "\n".join(text_parts)
                        elif isinstance(content, (dict, list)):
                             import json
                             current_step.output = json.dumps(content, indent=2)
                             current_step.language = "json"
                        else:
                            current_step.output = str(content)
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
