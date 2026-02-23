import os
import asyncio
import uuid
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage
from confluence_mcp.agent.client import MCPClient
from confluence_mcp.agent.graph import create_graph
from confluence_mcp.agent.memory import MemoryStore

import boto3

AGENT_LABELS = {
    "search":   "🔍 Search Agent",
    "writer":   "✍️  Writer Agent",
    "reviewer": "🔎 Reviewer Agent",
    "supervisor": "🧭 Supervisor",
    "bedrock":  "☁️ Bedrock Agent"
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
        cl.Starter(
            label="📜 Browse Past Conversations",
            message="/list_sessions",
            icon="/public/file.svg",
        ),
    ]

async def _initialize_session(resume_history=None):
    """Common initialization logic for new and resumed chats."""
    # 1. Provide a warning that Local MCP is bypassed for Bedrock
    # (The local MCP client is not needed since Bedrock calls the URL directly)
    cl.user_session.set("mcp_client", None)

    # 2. Get User Settings (Model Selection)
    provider = os.environ.get("LLM_PROVIDER", "openai")
    model = os.environ.get("LLM_MODEL", "gpt-4o")

    # 3. Initialize Bedrock Client
    bedrock_client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
    cl.user_session.set("bedrock_client", bedrock_client)

    # Store provider/model info for later use
    cl.user_session.set("llm_info", f"AWS_Bedrock/Claude-3-Haiku")

    # 4. Phase 2: Initialize Memory & Session
    memory_store = MemoryStore()
    cl.user_session.set("memory_store", memory_store)

    # Use thread_id from Chainlit for session tracking
    thread_id = cl.context.session.thread_id
    session_id = thread_id if thread_id else str(uuid.uuid4())
    cl.user_session.set("session_id", session_id)

    # Load history from resume or start fresh
    history = resume_history if resume_history else []
    cl.user_session.set("history", history)

    # Session metadata
    session_metadata = {
        "created_at": datetime.now().isoformat(),
        "provider": provider,
        "model": model,
    }
    cl.user_session.set("session_metadata", session_metadata)

    return True

@cl.on_chat_start
async def on_chat_start():
    """Initialize a new chat session."""
    success = await _initialize_session()
    if not success:
        return

    # Show welcome message for new sessions only
    llm_info = cl.user_session.get("llm_info")
    if llm_info and not cl.context.session.thread_id:
        # Only show for truly new sessions, not resumed ones
        pass  # Could add welcome message here

@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """Resume a previous chat session."""
    # Load conversation history from memory
    memory_store = MemoryStore()
    session_id = thread["id"]

    # Try to load from our memory store
    history = memory_store.load_session(session_id)

    # Initialize with the loaded history
    success = await _initialize_session(resume_history=history)
    if not success:
        return

    # Show resume message
    msg_count = len(history)
    await cl.Message(
        content=f"💬 Resumed conversation with {msg_count} previous messages",
        author="System"
    ).send()

@cl.on_message
async def on_message(message: cl.Message):
    # Handle special commands
    if message.content.strip() == "/list_sessions":
        memory_store = cl.user_session.get("memory_store")
        if not memory_store:
            memory_store = MemoryStore()

        sessions = memory_store.list_sessions()

        if not sessions:
            await cl.Message(content="📭 No previous conversations found.").send()
            return

        # Format the sessions list
        sessions_text = "📜 **Your Past Conversations:**\n\n"
        for i, session in enumerate(sessions[:10], 1):  # Show last 10
            created = session["created_at"][:19].replace("T", " ")
            updated = session["updated_at"][:19].replace("T", " ")
            msg_count = session["message_count"]
            sessions_text += f"{i}. **Session** `{session['id'][:8]}...`\n"
            sessions_text += f"   - Created: {created}\n"
            sessions_text += f"   - Last updated: {updated}\n"
            sessions_text += f"   - Messages: {msg_count}\n\n"

        sessions_text += "\n💡 **Tip:** In Chainlit, click the 🕐 history icon in the sidebar to browse and resume past conversations!"

        await cl.Message(content=sessions_text).send()
        return

    # Load history
    history = cl.user_session.get("history", [])
    history.append(HumanMessage(content=message.content))
    cl.user_session.set("history", history)

    # ---------------------------------------------------------
    # AgentCore (LangGraph + Bedrock Runtime) Execution Path
    # ---------------------------------------------------------
    try:
        mcp_client = cl.user_session.get("mcp_client")
        if not mcp_client:
            mcp_client = MCPClient()
            await mcp_client.connect()
            cl.user_session.set("mcp_client", mcp_client)
            
        from confluence_mcp.agent.bedrock_graph import create_bedrock_graph
        app = create_bedrock_graph(mcp_client)
        
        session_id = cl.user_session.get("session_id")
        config = {"configurable": {"thread_id": session_id}}
        
        # Graph execution loop
        state = {
            "messages": history,
            "session_id": session_id,
            "revision_count": 0,
            "reasoning_trace": []
        }
        
        config["recursion_limit"] = 50
        
        final_content = ""
        final_chunk = None
        
        async for chunk in app.astream(state, config=config, stream_mode="values"):
            final_chunk = chunk
            if "messages" in chunk:
                last_msg = chunk["messages"][-1]
                
                # Track the latest AI response content
                # Bedrock returns content as either a plain string OR a list of blocks
                # e.g. [{"type": "text", "text": "Here are your results..."}]
                if isinstance(last_msg, AIMessage) and not last_msg.tool_calls:
                    if isinstance(last_msg.content, str) and last_msg.content:
                        final_content = last_msg.content
                    elif isinstance(last_msg.content, list):
                        text_parts = [
                            block.get("text", "")
                            for block in last_msg.content
                            if isinstance(block, dict) and block.get("type") == "text"
                        ]
                        extracted = "\n".join(p for p in text_parts if p)
                        if extracted:
                            final_content = extracted
                
                # Log tool calls and agent activations to reasoning trace
                if "reasoning_trace" in chunk:
                    trace = chunk["reasoning_trace"]
                    if trace:
                        # Display the latest reasoning steps as Chainlit Steps
                        displayed = cl.user_session.get("displayed_steps", [])
                        for step_content in trace[len(displayed):]:
                            async with cl.Step(name="Agent Reasoning") as step:
                                step.output = step_content
                                await step.send()
                        cl.user_session.set("displayed_steps", trace)
        
        # Final history sync
        if final_chunk:
            cl.user_session.set("history", final_chunk["messages"])
        cl.user_session.set("displayed_steps", [])  # Reset for next message
        
        # Always send a final response message
        # This ensures the response is visible without requiring a second message
        await cl.Message(
            content=final_content if final_content else "✅ Done.",
            author="Confluence AI"
        ).send()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"Error in Bedrock AgentCore: {str(e)}").send()
        return

@cl.on_chat_end
async def on_chat_end():
    # Phase 2: Save final conversation state to memory
    memory_store = cl.user_session.get("memory_store")
    session_id = cl.user_session.get("session_id")
    history = cl.user_session.get("history", [])

    if memory_store and session_id and history:
        try:
            memory_store.save_session(session_id, history)
        except Exception as e:
            print(f"Warning: Failed to save session on exit: {e}")

    # Close MCP connection
    mcp_client = cl.user_session.get("mcp_client")
    if mcp_client:
        await mcp_client.close()
