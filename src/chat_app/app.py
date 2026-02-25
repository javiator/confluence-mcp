import os
import asyncio
import threading
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
    Invoke the hosted AgentCore agent with live token streaming.

    The runtime's async-generator entrypoint yields tokens as SSE events
    (data: "<token>"\\n\\n).  We parse those on a background thread and feed
    them into an asyncio.Queue so Chainlit can call stream_token() in real time.

    Falls back to reading the full body when the runtime returns plain JSON
    (e.g. old deployment still in place while the new image is rolling out).
    """
    if not AGENTCORE_AGENT_ID:
        await cl.Message(
            content="⚠️ AGENTCORE_AGENT_ID is not set in your .env file.",
            author="System"
        ).send()
        return

    bedrock_client = cl.user_session.get("bedrock_client")
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _stream():
        """
        Blocking I/O lives entirely in this thread.
        Parsed tokens are pushed onto the asyncio Queue via call_soon_threadsafe.
        A sentinel None signals the consumer that the stream is done.
        """
        try:
            resp = bedrock_client.invoke_agent_runtime(
                agentRuntimeArn=AGENTCORE_AGENT_ID,
                qualifier=AGENTCORE_AGENT_ALIAS_ID,
                runtimeSessionId=session_id,
                payload=json.dumps({
                    "prompt": user_message,
                    "sessionId": session_id,
                }),
                contentType="application/json",
            )
            content_type = resp.get("contentType", "")
            body = resp["response"]

            if "text/event-stream" in content_type:
                # SSE format: each event arrives as "data: <json>\n"
                # iter_lines() strips newlines and yields each non-empty line.
                for raw_line in body.iter_lines(chunk_size=256):
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8")
                    if not line.startswith("data: "):
                        continue
                    try:
                        token = json.loads(line[6:])
                        if isinstance(token, str) and token:
                            loop.call_soon_threadsafe(queue.put_nowait, token)
                    except json.JSONDecodeError:
                        pass
            else:
                # Non-streaming fallback: runtime returned plain JSON.
                # Unwrap {"result": "..."} if present.
                raw = body.read().decode("utf-8")
                try:
                    parsed = json.loads(raw)
                    content = (
                        parsed.get("result")
                        or parsed.get("message")
                        or raw
                    )
                except json.JSONDecodeError:
                    content = raw
                if content:
                    loop.call_soon_threadsafe(queue.put_nowait, content)

        except Exception as e:
            import traceback
            traceback.print_exc()
            loop.call_soon_threadsafe(queue.put_nowait, f"❌ AgentCore error: {e}")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    threading.Thread(target=_stream, daemon=True).start()

    msg = cl.Message(content="", author="Confluence AI")
    await msg.send()

    full_content = ""
    try:
        while True:
            token = await asyncio.wait_for(queue.get(), timeout=300)
            if token is None:
                break
            full_content += token
            await msg.stream_token(token)
    except asyncio.TimeoutError:
        await msg.stream_token("\n\n⚠️ Response timed out after 5 minutes.")

    await msg.update()

    if not full_content.strip():
        await msg.update()  # already sent; just ensure it's visible
        # Patch the empty message so the user sees something
        msg.content = "✅ Done (no text response returned)."
        await msg.update()

    # Persist to local Chainlit session history for resume
    history = cl.user_session.get("history", [])
    history.append(AIMessage(content=full_content))
    cl.user_session.set("history", history)


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
