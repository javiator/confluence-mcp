import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage
from confluence_mcp.agent.client import MCPClient
from confluence_mcp.agent.graph import create_graph
from confluence_mcp.agent.memory import MemoryStore

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
        cl.Starter(
            label="📜 Browse Past Conversations",
            message="/list_sessions",
            icon="/public/file.svg",
        ),
    ]

async def _initialize_session(resume_history=None):
    """Common initialization logic for new and resumed chats."""
    # 1. Connect to MCP Server (Session Scoped)
    mcp_client = MCPClient()
    try:
        await mcp_client.connect()
        cl.user_session.set("mcp_client", mcp_client)
    except Exception as e:
        await cl.Message(content=f"Failed to connect to MCP Server: {e}").send()
        return False

    # 2. Get User Settings (Model Selection)
    provider = os.environ.get("LLM_PROVIDER", "openai")
    model = os.environ.get("LLM_MODEL", "gpt-4o")

    # 3. Initialize Graph
    graph = create_graph(mcp_client, provider, model)
    cl.user_session.set("graph", graph)

    # Store provider/model info for later use
    cl.user_session.set("llm_info", f"{provider}/{model}")

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

    # ---------------------------------------------------------
    # Phase 3: CREWAI EXECUTION PATH
    # ---------------------------------------------------------
    try:
        from confluence_mcp.agent.frameworks.crewai_impl import create_confluence_crew
        from crewai import Task
        
        mcp_client = cl.user_session.get("mcp_client")
        provider = os.environ.get("LLM_PROVIDER", "openai")
        model = os.environ.get("LLM_MODEL", "gpt-4o")

        # Re-instantiate agents from factory
        crew_components = create_confluence_crew(mcp_client, provider, model)
        search_agent = crew_components["search_agent"]
        writer_agent = crew_components["writer_agent"]
        reviewer_agent = crew_components["reviewer_agent"]

        msg = cl.Message(content="")
        await msg.send()

        # Dynamic task mapping based on simple heuristics since CrewAI
        # needs explicit tasks. In production, a Router Agent would do this.
        user_input = message.content.lower()
        tasks = []

        if any(word in user_input for word in ["create", "update", "write", "draft"]):
            # Write + Review flow
            write_task = Task(
                description=f'Fulfill this user request to write/update documentation: "{message.content}"',
                agent=writer_agent,
                expected_output='Properly formatted Confluence XHTML content, drafted or published.'
            )
            review_task = Task(
                description='Review the drafted content from the writer. If it needs fixing, explain what must change. If it is good, approve it.',
                agent=reviewer_agent,
                expected_output='A review summary: APPROVED or NEEDS REVISION.',
                context=[write_task]
            )
            tasks = [write_task, review_task]
        else:
            # Default to Search
            search_task = Task(
                description=f'Find information to answer this user query: "{message.content}"',
                agent=search_agent,
                expected_output='A summary of findings with Confluence page titles and URLs.'
            )
            tasks = [search_task]

        from crewai import Crew, Process
        active_crew = Crew(
            agents=[search_agent, writer_agent, reviewer_agent],
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        )

        # CrewAI execution is synchronous, so we run it in a thread to not block Chainlit UI
        # We use cl.make_async to run sync code asynchronously
        result = await cl.make_async(active_crew.kickoff)()

        await msg.stream_token(str(result.raw))
        
    except Exception as e:
        await cl.Message(content=f"Error executing CrewAI: {str(e)}").send()
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
