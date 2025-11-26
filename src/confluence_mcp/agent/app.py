import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage
from .client import MCPClient
from .graph import create_graph
import os

# Global MCP Client
mcp_client = MCPClient()

@cl.on_chat_start
async def on_chat_start():
    # 1. Connect to MCP Server
    try:
        await mcp_client.connect()
        cl.user_session.set("mcp_client", mcp_client)
    except Exception as e:
        await cl.Message(content=f"Failed to connect to MCP Server: {e}").send()
        return

    # 2. Get User Settings (Model Selection)
    # For now, we default to OpenAI/GPT-4o or environment variables
    # We could use cl.ChatSettings to make this interactive
    
    provider = os.environ.get("LLM_PROVIDER", "openai")
    model = os.environ.get("LLM_MODEL", "gpt-4o")
    
    # 3. Initialize Graph
    graph = create_graph(mcp_client, provider, model)
    cl.user_session.set("graph", graph)
    
    await cl.Message(content=f"Connected to Confluence MCP! Using {provider}/{model}.").send()

@cl.on_message
async def on_message(message: cl.Message):
    graph = cl.user_session.get("graph")
    
    # Maintain conversation history in session
    history = cl.user_session.get("history", [])
    history.append(HumanMessage(content=message.content))
    
    inputs = {"messages": history}
    
    msg = cl.Message(content="")
    await msg.send()
    
    # We will track the current tool step to update it
    current_step = None
    
    async for event in graph.astream_events(inputs, version="v1"):
        kind = event["event"]
        
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                await msg.stream_token(content)
                
        elif kind == "on_tool_start":
            # Create a new step for the tool
            tool_name = event["name"]
            tool_input = event["data"].get("input")
            
            current_step = cl.Step(name=tool_name, type="tool")
            current_step.input = tool_input
            await current_step.send()
            
        elif kind == "on_tool_end":
            if current_step:
                tool_output = event["data"].get("output")
                # If output is a ToolMessage, extract content
                if hasattr(tool_output, "content"):
                    current_step.output = tool_output.content
                else:
                    current_step.output = str(tool_output)
                await current_step.update()
                current_step = None

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
    await mcp_client.close()
