import logging
import os
import json
import boto3
from typing import List, Dict, Any, Union, Optional, Annotated, TypedDict

os.environ["AWS_DEFAULT_REGION"] = os.environ.get("AWS_REGION", "us-east-1")

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Implementation of missing SDK components ──────────────────────────────────

class MemoryClient:
    """Manages session history using bedrock-agentcore SDK and local fallback."""
    def __init__(self, memory_id: Optional[str] = None):
        self.memory_id = memory_id
        self._local_history = {}
        self.manager = None
        if memory_id:
            try:
                from bedrock_agentcore.memory import MemorySessionManager
                self.manager = MemorySessionManager(memory_id=memory_id)
                logger.info(f"Initialized MemorySessionManager with ID: {memory_id}")
            except Exception as e:
                logger.error(f"Failed to load MemorySessionManager: {e}")

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        if self.manager:
            try:
                # In a real scenario, we'd fetch from session.list_events()
                # For now, we use the local fallback to ensure stability
                pass
            except Exception as e:
                logger.warning(f"Failed to fetch from memory service: {e}")
        
        return self._local_history.get(session_id, [])

    def save_message(self, session_id: str, role: str, content: str):
        if session_id not in self._local_history:
            self._local_history[session_id] = []
        self._local_history[session_id].append({"role": role, "content": content})
        logger.info(f"Saved {role} message to session {session_id}")

# MCP Gateway integration is handled by langchain_mcp_adapters
# Tools are automatically discovered from the AgentCore Gateway

# ── App Initialization ────────────────────────────────────────────────────────

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

# Attach memory component
app.memory = MemoryClient(os.environ.get("AGENTCORE_MEMORY_ID"))

# ── Agent Logic ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Confluence Assistant.
Your primary job is to SEARCH for pages and PUBLISH new content.

CRITICAL OPERATIONAL RULES:
1. SILENT TOOL CALLS: DO NOT speak, acknowledge, or explain before calling a tool. If your next step is a tool call, respond ONLY with that tool call.
2. MANDATORY PAYLOAD: The argument for XHTML content is 'xhtml_payload' for creation and 'page_content_xhtml' for updates.
3. NEVER OMIT the payload. It is required for the tool to function.
4. You MUST provide the full, final XHTML in the first tool call. No placeholders.

STABILIZED WORKFLOW:
- SEARCH: search_confluence(query="...")
- CREATE: execute_confluence_publish(space_key="...", parent_id="...", title="...", xhtml_payload="...")
- UPDATE: update_page_full(page_id="...", page_content_xhtml="...")
- APPEND: append_to_page(page_id="...", page_content_xhtml="...")

FORMATTING RULES:
- Use strictly valid Confluence storage format (XHTML).
- DO NOT USE MARKDOWN within tool payloads (e.g., **, ##).
- DO NOT encode HTML entities (like &lt;, &gt;, &quot;, &amp;) manually. ALWAYS use literal characters (e.g., <, >, ", &).
- CODE BLOCKS: Use <ac:structured-macro ac:name="code"> with <ac:plain-text-body><![CDATA[...]]> inside. ALWAYS close CDATA with ]]> IMMEDIATELY before </ac:plain-text-body>.
- TABLE OF CONTENTS: Use <ac:structured-macro ac:name="toc"/> at the top."""

# Essential type for add_messages
def dummy_add_messages(left, right): return left + right

class AgentState(TypedDict):
    messages: Annotated[List[Any], dummy_add_messages]

def repair_history_for_bedrock(messages: List[Any]) -> List[Any]:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
    if not messages: return []
    msgs = [m for m in messages if not isinstance(m, SystemMessage)]
    if not msgs: return []
    repaired = []
    if not isinstance(msgs[0], HumanMessage):
        repaired.append(HumanMessage(content="Hello"))
    
    for m in msgs:
        if not repaired:
            repaired.append(m)
            continue
        prev = repaired[-1]
        if isinstance(m, ToolMessage):
            if not isinstance(prev, AIMessage) or not prev.tool_calls:
                repaired.append(AIMessage(content="", tool_calls=[{"name": m.name or "tool", "args": {}, "id": m.tool_call_id}]))
        elif isinstance(m, HumanMessage) and isinstance(prev, (HumanMessage, ToolMessage)):
            prev.content = f"{prev.content}\n\n{m.content}"
            continue
        elif isinstance(m, AIMessage) and isinstance(prev, AIMessage):
            prev.content = f"{prev.content}\n\n{m.content}"
            continue
        repaired.append(m)
    return repaired

@app.entrypoint
def invoke(payload):
    # Deferred heavy imports
    import asyncio
    from langchain_aws import ChatBedrock
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolNode

    user_message = payload.get("prompt", "")
    session_id = payload.get("sessionId", "default")
    logger.info(f"Agent invoked for session: {session_id}")

    # 1. Retrieve history
    history = app.memory.get_session_history(session_id)
    messages = []
    for h in history:
        if h["role"] == "user": messages.append(HumanMessage(content=h["content"]))
        else: messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=user_message))

    # 2. Setup LLM
    # Default to Claude 3 Haiku for cost savings, but allow override via env var
    model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    logger.info(f"Using model: {model_id}")

    llm = ChatBedrock(
        model_id=model_id,
        model_kwargs={"temperature": 0},
        region_name=os.environ.get("AWS_REGION", "us-east-1")
    )

    # 3. Run the async agent execution with MCP session kept alive
    async def run_agent():
        from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
        from mcp import ClientSession
        from langchain_mcp_adapters.tools import load_mcp_tools

        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        gateway_url = os.environ.get(
            "CONFLUENCE_GATEWAY_URL",
            "https://confluence-agentcore-gateway-pejofakb0g.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
        )

        # Create AWS IAM authenticated MCP client
        mcp_client = aws_iam_streamablehttp_client(
            endpoint=gateway_url,
            aws_region=aws_region,
            aws_service="bedrock-agentcore"
        )

        # Keep the MCP session alive during entire agent execution
        async with mcp_client as (read, write, session_id_callback):
            async with ClientSession(read, write) as session:
                # Initialize and load tools
                await session.initialize()
                tools = await load_mcp_tools(session)
                logger.info(f"Loaded {len(tools)} tools from MCP Gateway")

                # Bind tools to LLM
                llm_with_tools = llm.bind_tools(tools)

                # Build LangGraph workflow
                workflow = StateGraph(AgentState)

                async def agent_node(state):
                    repaired = repair_history_for_bedrock(state["messages"])
                    prompt = [SystemMessage(content=SYSTEM_PROMPT)] + repaired
                    response = await llm_with_tools.ainvoke(prompt)
                    return {"messages": [response]}

                tool_node = ToolNode(tools)

                workflow.add_node("agent", agent_node)
                workflow.add_node("tools", tool_node)
                workflow.set_entry_point("agent")

                def should_continue(state):
                    last = state["messages"][-1]
                    return "tools" if last.tool_calls else END

                workflow.add_conditional_edges("agent", should_continue)
                workflow.add_edge("tools", "agent")

                # Execute graph with MCP session still alive
                graph = workflow.compile()
                final_state = await graph.ainvoke({"messages": messages})
                return final_state["messages"][-1].content

    # Execute async agent
    final_response = asyncio.run(run_agent())

    # 4. Save history
    app.memory.save_message(session_id, "user", user_message)
    app.memory.save_message(session_id, "assistant", final_response)

    return {"result": final_response}

if __name__ == "__main__":
    app.run()
