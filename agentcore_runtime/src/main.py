import logging
import os
import json
import boto3
from typing import List, Dict, Any, Union, Annotated, TypedDict

os.environ["AWS_DEFAULT_REGION"] = os.environ.get("AWS_REGION", "us-east-1")

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Memory ────────────────────────────────────────────────────────────────────

class MemoryClient:
    """
    Session memory backed by AgentCore MemorySessionManager when
    AGENTCORE_MEMORY_ID is set, with an in-container dict as fallback.

    To enable persistent memory:
      1. Run `agentcore configure` to create the Memory resource and populate
         .bedrock_agentcore.yaml with memory_id.
      2. Deploy with `agentcore deploy --env AGENTCORE_MEMORY_ID=<id>`.
    """
    def __init__(self):
        self._local: Dict[str, List[Dict[str, Any]]] = {}
        self.memory_id = os.environ.get("AGENTCORE_MEMORY_ID")
        self.manager = None
        if self.memory_id:
            try:
                from bedrock_agentcore.memory.session import MemorySessionManager
                self.manager = MemorySessionManager(
                    memory_id=self.memory_id,
                    region_name=os.environ.get("AWS_REGION", "us-east-1"),
                )
                logger.info(f"AgentCore MemorySessionManager initialised: {self.memory_id}")
            except Exception as e:
                logger.warning(f"MemorySessionManager init failed, using local fallback: {e}")

    def _open_session(self, session_id: str, actor_id: str):
        """Return a MemorySession for the given IDs (creates if absent)."""
        return self.manager.create_memory_session(
            actor_id=actor_id, session_id=session_id
        )

    def get_session_history(self, session_id: str, actor_id: str = "default") -> List[Dict[str, Any]]:
        if self.manager:
            try:
                session = self._open_session(session_id, actor_id)
                turns = session.get_last_k_turns(k=20)
                messages: List[Dict[str, Any]] = []
                for turn in turns:
                    items = turn if isinstance(turn, list) else [turn]
                    for msg in items:
                        role = (msg.get("role") or "").lower()
                        content = msg.get("content") or ""
                        if role and content:
                            messages.append({"role": role, "content": content})
                return messages
            except Exception as e:
                logger.warning(f"Memory retrieval failed, using local fallback: {e}")
        return self._local.get(session_id, [])

    def save_turn(self, session_id: str, user_content: str, assistant_content: str,
                  actor_id: str = "default"):
        """Save a complete user + assistant turn atomically."""
        # Always keep local cache up to date (used as fallback)
        bucket = self._local.setdefault(session_id, [])
        bucket.append({"role": "user", "content": user_content})
        bucket.append({"role": "assistant", "content": assistant_content})

        if self.manager:
            try:
                from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole
                session = self._open_session(session_id, actor_id)
                session.add_turns(messages=[
                    ConversationalMessage(user_content, MessageRole.USER),
                    ConversationalMessage(assistant_content, MessageRole.ASSISTANT),
                ])
                logger.info(f"Saved turn to AgentCore memory: session={session_id}")
            except Exception as e:
                logger.warning(f"Memory save failed (turn kept locally): {e}")

# ── App Initialization ────────────────────────────────────────────────────────

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()
app.memory = MemoryClient()

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
async def invoke(payload, context):
    """
    Async-generator entrypoint — yields string tokens as the LangGraph ReAct
    loop produces them.  The AgentCore runtime streams each token to the caller
    as a Server-Sent Event (data: "<token>"\\n\\n).

    The optional `context` parameter is injected by the SDK and carries
    context.session_id and context.actor_id when available.
    """
    # Deferred heavy imports keep cold-start overhead low
    from langchain_aws import ChatBedrock
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolNode
    from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
    from mcp import ClientSession
    from langchain_mcp_adapters.tools import load_mcp_tools

    # ── Session identity ──────────────────────────────────────────────────────
    # Prefer the SDK-injected context IDs; fall back to payload fields.
    session_id = (
        (getattr(context, "session_id", None) if context else None)
        or payload.get("sessionId", "default")
    )
    actor_id = (
        (getattr(context, "actor_id", None) if context else None)
        or "default"
    )
    user_message = payload.get("prompt", "")
    logger.info(f"Agent invoked: session={session_id} actor={actor_id}")

    # ── History ───────────────────────────────────────────────────────────────
    history = app.memory.get_session_history(session_id, actor_id)
    messages = []
    for h in history:
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        else:
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=user_message))

    # ── LLM ───────────────────────────────────────────────────────────────────
    model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    logger.info(f"Using model: {model_id}")
    llm = ChatBedrock(
        model_id=model_id,
        model_kwargs={"temperature": 0},
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )

    # ── MCP + LangGraph streaming ─────────────────────────────────────────────
    gateway_url = os.environ.get(
        "CONFLUENCE_GATEWAY_URL",
        "https://confluence-agentcore-gateway-pejofakb0g.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
    )
    aws_region = os.environ.get("AWS_REGION", "us-east-1")

    mcp_client = aws_iam_streamablehttp_client(
        endpoint=gateway_url,
        aws_region=aws_region,
        aws_service="bedrock-agentcore",
    )

    full_response = ""

    async with mcp_client as (read, write, _):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()
            tools = await load_mcp_tools(mcp_session)
            logger.info(f"Loaded {len(tools)} tools from MCP Gateway")

            llm_with_tools = llm.bind_tools(tools)

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

            graph = workflow.compile()

            # Stream token-by-token from the LangGraph event stream.
            # on_chat_model_stream fires for every LLM token across all turns.
            # Tool-call turns produce empty or list content, so only non-empty
            # strings reach the caller (the final answer).
            async for event in graph.astream_events({"messages": messages}, version="v2"):
                if event["event"] != "on_chat_model_stream":
                    continue
                chunk = event["data"]["chunk"]
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    full_response += content
                    yield content
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                full_response += text
                                yield text

    # ── Persist turn ──────────────────────────────────────────────────────────
    # Runs after all tokens have been yielded to the caller.
    app.memory.save_turn(session_id, user_message, full_response, actor_id)
    logger.info(f"Turn complete: {len(full_response)} chars, session={session_id}")


if __name__ == "__main__":
    app.run()
