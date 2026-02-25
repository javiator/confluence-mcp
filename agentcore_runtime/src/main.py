import logging
import os
import json
import boto3
import sys
import traceback
from typing import List, Dict, Any, Union, Annotated, TypedDict

os.environ["AWS_DEFAULT_REGION"] = os.environ.get("AWS_REGION", "us-east-1")

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── App Initialization ────────────────────────────────────────────────────────

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

# ── Agent Logic ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Confluence Assistant.
Your primary job is to SEARCH for pages and PUBLISH new content.

CRITICAL OPERATIONAL RULES:
1. SILENT TOOL CALLS: DO NOT speak, acknowledge, or explain before calling a tool. If your next step is a tool call, respond ONLY with that tool call.
2. MANDATORY PAYLOAD: The argument for XHTML content is 'xhtml_payload' for creation and 'page_content_xhtml' for updates.
3. NEVER OMIT the payload. It is required for the tool to function.
4. You MUST provide the full, final XHTML in the first tool call. No placeholders.

STABILIZED WORKFLOW:
- SEARCH: confluence-mcp-lambda___search_confluence(query="...")
- CREATE: confluence-mcp-lambda___execute_confluence_publish(space_key="...", parent_id="...", title="...", xhtml_payload="...")
- UPDATE: confluence-mcp-lambda___update_page_full(page_id="...", page_content_xhtml="...")
- APPEND: confluence-mcp-lambda___append_to_page(page_id="...", page_content_xhtml="...")

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
            p_content = prev.content if isinstance(prev.content, str) else str(prev.content)
            m_content = m.content if isinstance(m.content, str) else str(m.content)
            prev.content = f"{p_content}\n\n{m_content}"
            continue
        elif isinstance(m, AIMessage) and isinstance(prev, AIMessage):
            p_content = prev.content if isinstance(prev.content, str) else str(prev.content)
            m_content = m.content if isinstance(m.content, str) else str(m.content)
            prev.content = f"{p_content}\n\n{m_content}"
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
    from langgraph_checkpoint_aws import AgentCoreMemorySaver
    from langgraph.checkpoint.memory import MemorySaver
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
    user_message = payload.get("prompt", "") or payload.get("message", "") # Support both
    logger.info(f"Agent invoked: session={session_id} actor={actor_id} prompt='{user_message}'")

    # ── Memory ───────────────────────────────────────────────────────────────
    memory_id = os.environ.get("AGENTCORE_MEMORY_ID")
    checkpointer = None
    if memory_id:
        try:
            checkpointer = AgentCoreMemorySaver(
                memory_id=memory_id,
                region_name=os.environ.get("AWS_REGION", "us-east-1")
            )
            logger.info(f"AgentCoreMemorySaver initialized: {memory_id}")
        except Exception as e:
            logger.warning(f"AgentCoreMemorySaver init failed, using local fallback: {e}")
            checkpointer = MemorySaver()
    else:
        logger.info("No AGENTCORE_MEMORY_ID found, using volatile MemorySaver")
        checkpointer = MemorySaver()

    if not user_message:
        user_message = "Hello"

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
    logger.info(f"Targeting MCP Gateway: {gateway_url} in {aws_region}")

    mcp_client = aws_iam_streamablehttp_client(
        endpoint=gateway_url,
        aws_region=aws_region,
        aws_service="bedrock-agentcore",
    )

    full_response = ""

    async with mcp_client as (read, write, _):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()
            logger.info("MCP Session initialized. Fetching tools...")
            tools = await load_mcp_tools(mcp_session)
            tool_names = [t.name for t in tools]
            logger.info(f"Discovery complete. Loaded {len(tools)} tools: {tool_names}")
            
            if len(tools) == 0:
                logger.error("CRITICAL: 0 tools loaded! Agent will have no capabilities.")

            llm_with_tools = llm.bind_tools(tools)

            workflow = StateGraph(AgentState)

            async def agent_node(state):
                repaired = repair_history_for_bedrock(state["messages"])
                prompt = [SystemMessage(content=SYSTEM_PROMPT)] + repaired
                # ainvoke is safer for preserving tool_calls and complex content.
                # The token-by-token streaming is handled by the astream_events loop fallback.
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

            graph = workflow.compile(checkpointer=checkpointer)

            # Stream from the LangGraph event stream.
            logger.info("Starting astream_events loop")
            config = {"configurable": {"thread_id": session_id, "actor_id": actor_id}}
            async for event in graph.astream_events({"messages": [HumanMessage(content=user_message)]}, config, version="v2"):
                kind = event["event"]
                # logger.debug(f"Event: {kind} {event.get('name')}") # Too noisy for prod, but good for debug
                
                if kind == "on_chat_model_stream":
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
                elif kind == "on_chat_model_end" and not full_response:
                    output = event["data"]["output"]
                    content = getattr(output, "content", None)
                    logger.info(f"on_chat_model_end triggered. Content: {content}")
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
                            elif isinstance(block, str):
                                full_response += block
                                yield block
                elif kind == "on_chain_end" and event.get("name") == "LangGraph" and not full_response:
                    # Final fallback: extract the last message from the state
                    output = event["data"]["output"]
                    if "messages" in output:
                        last_msg = output["messages"][-1]
                        if isinstance(last_msg, AIMessage) and last_msg.content:
                            logger.info("Captured response from on_chain_end")
                            full_response = last_msg.content
                            yield full_response
            
            if not full_response:
                logger.warning("astream_events loop finished with empty full_response")

    logger.info(f"Turn complete: {len(full_response)} chars, session={session_id}")


if __name__ == "__main__":
    app.run()
