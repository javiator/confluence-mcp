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
    # Phase 4: AWS BEDROCK EXECUTION PATH
    # ---------------------------------------------------------
    try:
        bedrock_client = cl.user_session.get("bedrock_client")
        session_id = cl.user_session.get("session_id")
        
        # Hardcoding the Agent ID we deployed via Terraform
        # In a real app, this might come from an env var
        AGENT_ID = "N2YKHR0RUU"
        AGENT_ALIAS_ID = "TSTALIASID" # Default alias for DRAFT version
        
        # We need a separate message to update during streaming
        msg = cl.Message(content="", author="Bedrock Agent")
        await msg.send()
        
        # Invoke the Bedrock Agent
        # Because boto3 is synchronous, we run it in a thread to keep UI responsive
        def invoke_agent():
            return bedrock_client.invoke_agent(
                agentId=AGENT_ID,
                agentAliasId=AGENT_ALIAS_ID,
                sessionId=session_id,
                inputText=message.content,
            )
            
        response = await cl.make_async(invoke_agent)()
        
        completion = ""
        # The response is an event stream
        for event in response.get("completion"):
            # Check if this event contains a chunk of text
            if "chunk" in event:
                chunk_data = event["chunk"].get("bytes")
                if chunk_data:
                    chunk_str = chunk_data.decode("utf-8")
                    completion += chunk_str
                    await msg.stream_token(chunk_str)
            
            # Optionally: we could trace the orchestrator events here to show
            # when Bedrock is calling the Lambda tool!
            elif "trace" in event:
                trace_obj = event["trace"].get("trace", {})
                if "orchestrationTrace" in trace_obj:
                    orch_trace = trace_obj["orchestrationTrace"]
                    if "invocationInput" in orch_trace:
                        tool_name = orch_trace["invocationInput"].get("actionGroupInvocationInput", {}).get("function")
                        if tool_name:
                            # Show a temporary status in Chainlit
                            asyncio.create_task(
                                cl.Message(content=f"🛠️ Tool call: `{tool_name}`", author="System").send()
                            )

        # Update history with the final result
        history.append(AIMessage(content=completion))
        cl.user_session.set("history", history)
        
    except Exception as e:
        await cl.Message(content=f"Error executing AWS Bedrock Agent: {str(e)}").send()
        return

    # Phase 2: Save conversation to memory after each exchange
    memory_store = cl.user_session.get("memory_store")
    session_id = cl.user_session.get("session_id")
    if memory_store and session_id:
        try:
            memory_store.save_session(session_id, history)
        except Exception as e:
            # Don't fail the conversation if memory save fails, just log
            print(f"Warning: Failed to save session to memory: {e}")

    await msg.update()

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
