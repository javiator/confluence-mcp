import os
import asyncio
import uuid
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage
from chat_app.client import MCPClient
from chat_app.graph import create_graph
from chat_app.memory import MemoryStore

import boto3

# ── AgentCore configuration ───────────────────────────────────────────────────
# Set USE_AGENTCORE=true in .env to route messages to the hosted AgentCore agent
# instead of running the LangGraph loop locally.
USE_AGENTCORE = os.environ.get("USE_AGENTCORE", "false").lower() == "true"
AGENTCORE_AGENT_ID = os.environ.get("AGENTCORE_AGENT_ID", "")
AGENTCORE_AGENT_ALIAS_ID = os.environ.get("AGENTCORE_AGENT_ALIAS_ID", "TSTALIASID")

AGENT_LABELS = {
    "search":   "🔍 Search Agent",
    "writer":   "✍️  Writer Agent",
    "reviewer": "🔎 Reviewer Agent",
    "supervisor": "🧭 Supervisor",
    "bedrock":  "☁️ Bedrock Agent"
}

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
    # In AgentCore mode the local MCPClient is not needed — AgentCore
    # handles tool calls itself via the Gateway.
    cl.user_session.set("mcp_client", None)

    # Bedrock runtime client (used for AgentCore invocation)
    # AgentCore uses a specific data-plane endpoint
    bedrock_client = boto3.client(
        "bedrock-agentcore", 
        region_name="us-east-1",
        endpoint_url="https://bedrock-agentcore.us-east-1.amazonaws.com"
    )
    cl.user_session.set("bedrock_client", bedrock_client)

    mode = "AgentCore (cloud)" if USE_AGENTCORE else "LangGraph (local)"
    cl.user_session.set("llm_info", f"AWS_Bedrock / {mode}")

    # Initialize Memory & Session
    memory_store = MemoryStore()
    cl.user_session.set("memory_store", memory_store)

    thread_id = cl.context.session.thread_id
    session_id = thread_id if thread_id else str(uuid.uuid4())
    cl.user_session.set("session_id", session_id)

    history = resume_history if resume_history else []
    cl.user_session.set("history", history)

    cl.user_session.set("session_metadata", {
        "created_at": datetime.now().isoformat(),
        "mode": mode,
    })

    return True

@cl.on_chat_start
async def on_chat_start():
    """Initialize a new chat session."""
    await _initialize_session()

@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """Resume a previous chat session."""
    memory_store = MemoryStore()
    session_id = thread["id"]
    history = memory_store.load_session(session_id)

    success = await _initialize_session(resume_history=history)
    if not success:
        return

    msg_count = len(history)
    await cl.Message(
        content=f"💬 Resumed conversation with {msg_count} previous messages",
        author="System"
    ).send()

@cl.on_message
async def on_message(message: cl.Message):
    # ── Special commands ──────────────────────────────────────────────────────
    if message.content.strip() == "/list_sessions":
        memory_store = cl.user_session.get("memory_store")
        if not memory_store:
            memory_store = MemoryStore()

        sessions = memory_store.list_sessions()

        if not sessions:
            await cl.Message(content="📭 No previous conversations found.").send()
            return

        sessions_text = "📜 **Your Past Conversations:**\n\n"
        for i, session in enumerate(sessions[:10], 1):
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

    # ── Track local history (for session resumption display) ──────────────────
    history = cl.user_session.get("history", [])
    history.append(HumanMessage(content=message.content))
    cl.user_session.set("history", history)

    session_id = cl.user_session.get("session_id")

    # ── Execution path selection ──────────────────────────────────────────────
    if USE_AGENTCORE:
        await _run_agentcore(message.content, session_id)
    else:
        await _run_local(message.content, session_id, history)


async def _run_agentcore(user_message: str, session_id: str):
    """
    Invoke the hosted AgentCore agent.

    AgentCore manages the full ReAct loop and tool calls (via the Gateway
    pointing at the Lambda MCP server).  We just pass the user message and
    collect the streamed response.
    """
    if not AGENTCORE_AGENT_ID:
        await cl.Message(
            content="⚠️ AGENTCORE_AGENT_ID is not set in your .env file. See AGENTCORE_MIGRATION.md.",
            author="System"
        ).send()
        return

    bedrock_client = cl.user_session.get("bedrock_client")

    try:
        # boto3 invoke_agent_runtime is synchronous — run it in a thread so we don't
        # block the Chainlit event loop.
        def _call_agent():
            return bedrock_client.invoke_agent_runtime(
                agentRuntimeArn=AGENTCORE_AGENT_ID,
                qualifier=AGENTCORE_AGENT_ALIAS_ID,
                runtimeSessionId=session_id,
                payload=json.dumps({
                    "prompt": user_message,
                    "sessionId": session_id
                }),
                contentType="application/json",
            )

        response = await asyncio.to_thread(_call_agent)

        # Collect streamed response chunks
        final_content = ""
        # The response payload is in the "response" field for AgentCore
        for event in response.get("response", []):
            if isinstance(event, str):
                final_content += event
            elif isinstance(event, dict):
                # Handle potential JSON objects in the stream
                final_content += json.dumps(event, indent=2) + "\n\n"
            elif isinstance(event, bytes):
                final_content += event.decode("utf-8")

        # Clean up JSON wrapping if present
        display_content = final_content
        try:
            # The agent often returns a JSON string like {"result": "..."}
            parsed = json.loads(final_content)
            if isinstance(parsed, dict) and "result" in parsed:
                display_content = parsed["result"]
            elif isinstance(parsed, dict) and "message" in parsed:
                display_content = parsed["message"]
        except json.JSONDecodeError:
            # Not JSON or partial JSON, use as is
            pass

        if not display_content:
            display_content = "✅ Done (no text response returned)."

        await cl.Message(content=display_content, author="Confluence AI").send()

        # Persist to local memory for Chainlit session resume
        history = cl.user_session.get("history", [])
        history.append(AIMessage(content=final_content))
        cl.user_session.set("history", history)

    except Exception as e:
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"❌ AgentCore error: {str(e)}").send()


async def _run_local(user_message: str, session_id: str, history: list):
    """
    Run the LangGraph agent locally (development / fallback mode).
    Uses bedrock_graph.py which calls ChatBedrock + local MCP stdio.
    """
    try:
        mcp_client = cl.user_session.get("mcp_client")
        if not mcp_client:
            mcp_client = MCPClient()
            await mcp_client.connect()
            cl.user_session.set("mcp_client", mcp_client)

        from chat_app.bedrock_graph import create_bedrock_graph
        app = create_bedrock_graph(mcp_client)

        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}

        state = {
            "messages": history,
            "session_id": session_id,
            "revision_count": 0,
            "reasoning_trace": []
        }

        final_content = ""
        final_chunk = None

        async for chunk in app.astream(state, config=config, stream_mode="values"):
            final_chunk = chunk
            if "messages" in chunk:
                last_msg = chunk["messages"][-1]

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

                if "reasoning_trace" in chunk:
                    trace = chunk["reasoning_trace"]
                    if trace:
                        displayed = cl.user_session.get("displayed_steps", [])
                        for step_content in trace[len(displayed):]:
                            async with cl.Step(name="Agent Reasoning") as step:
                                step.output = step_content
                                await step.send()
                        cl.user_session.set("displayed_steps", trace)

        if final_chunk:
            cl.user_session.set("history", final_chunk["messages"])
        cl.user_session.set("displayed_steps", [])

        await cl.Message(
            content=final_content if final_content else "✅ Done.",
            author="Confluence AI"
        ).send()

    except Exception as e:
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"❌ Local agent error: {str(e)}").send()


@cl.on_chat_end
async def on_chat_end():
    memory_store = cl.user_session.get("memory_store")
    session_id = cl.user_session.get("session_id")
    history = cl.user_session.get("history", [])

    if memory_store and session_id and history:
        try:
            memory_store.save_session(session_id, history)
        except Exception as e:
            print(f"Warning: Failed to save session on exit: {e}")

    # Close MCP connection (only used in local mode)
    mcp_client = cl.user_session.get("mcp_client")
    if mcp_client:
        await mcp_client.close()
