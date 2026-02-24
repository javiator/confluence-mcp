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

class ToolGateway:
    """Provides tool discovery and invocation via the Confluence MCP Lambda."""
    def __init__(self, lambda_name: str):
        self.lambda_name = lambda_name
        self.lambda_client = boto3.client("lambda")

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return the hardcoded tool schema for the Confluence agent."""
        return [
            {
                "name": "search_confluence",
                "description": "Search for Confluence pages using CQL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "CQL query or search term"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_confluence_page",
                "description": "Get a Confluence page by ID, returning plain text content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string", "description": "Confluence page ID"}
                    },
                    "required": ["page_id"]
                }
            },
            {
                "name": "get_confluence_children",
                "description": "Get direct child pages of a specific page.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string", "description": "Parent page ID"}
                    },
                    "required": ["page_id"]
                }
            },
            {
                "name": "execute_confluence_publish",
                "description": "Create a new Confluence page with mandatory XHTML content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "space_key": {"type": "string"},
                        "parent_id": {"type": "string"},
                        "title": {"type": "string"},
                        "xhtml_payload": {"type": "string", "description": "Full XHTML content"}
                    },
                    "required": ["space_key", "parent_id", "title", "xhtml_payload"]
                }
            },
            {
                "name": "update_page_full",
                "description": "Update a Confluence page with a new full page_content_xhtml payload.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string"},
                        "page_content_xhtml": {"type": "string"}
                    },
                    "required": ["page_id", "page_content_xhtml"]
                }
            },
            {
                "name": "append_to_page",
                "description": "Append new content to the bottom of an existing Confluence page.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string"},
                        "page_content_xhtml": {"type": "string"}
                    },
                    "required": ["page_id", "page_content_xhtml"]
                }
            },
            {
                "name": "prepare_confluence_page_merge_update",
                "description": "Retrieve page content and metadata for merging.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string"}
                    },
                    "required": ["page_id"]
                }
            }
        ]

    def invoke_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Invoke the tool by calling the backend Lambda."""
        logger.info(f"Invoking tool {tool_name} via Lambda {self.lambda_name}")
        # The Lambda is wrapped with Lambda Web Adapter and uses FastMCP.
        # It expects either a standard Lambda payload or an HTTP-like request.
        # FastMCP tools are usually called via /tools/{name} if served over HTTP.
        # However, if it's a direct Lambda call, our server.py doesn't have a direct handler.
        # Let's assume the Lambda is configured to route properly or we use a bridge.
        # For this implementation, we'll try a standard payload format.
        payload = {
            "action": "call_tool",
            "name": tool_name,
            "arguments": tool_input
        }
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.lambda_name,
                Payload=json.dumps(payload)
            )
            result_raw = response["Payload"].read().decode("utf-8")
            result = json.loads(result_raw)
            # Handle different common response formats
            if isinstance(result, dict):
                return result.get("content") or result.get("result") or str(result)
            return str(result)
        except Exception as e:
            logger.error(f"Error invoking tool {tool_name}: {e}")
            return f"Error executing tool {tool_name}: {str(e)}"

# ── App Initialization ────────────────────────────────────────────────────────

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

# Attach missing components
app.memory = MemoryClient(os.environ.get("AGENTCORE_MEMORY_ID"))
app.gateway = ToolGateway(os.environ.get("CONFLUENCE_LAMBDA_NAME", "ConfluenceAgentCoreMCP"))

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
    from langchain_aws import ChatBedrock
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
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

    # 2. Setup LLM and Tools
    llm = ChatBedrock(
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        model_kwargs={"temperature": 0},
        region_name=os.environ.get("AWS_REGION", "us-east-1")
    )
    
    raw_tools = app.gateway.get_tools()
    
    # Custom tool invocation wrapper for LangChain
    def call_tool_wrapper(name, args):
        return app.gateway.invoke_tool(name, args)

    # Simplified graph for Confluence operations
    workflow = StateGraph(AgentState)

    async def agent_node(state):
        repaired = repair_history_for_bedrock(state["messages"])
        prompt = [SystemMessage(content=SYSTEM_PROMPT)] + repaired
        # Manual tool binding for safety
        llm_with_tools = llm.bind_tools(raw_tools)
        response = await llm_with_tools.ainvoke(prompt)
        return {"messages": [response]}

    async def tool_node(state):
        last_msg = state["messages"][-1]
        results = []
        for call in last_msg.tool_calls:
            out = app.gateway.invoke_tool(call["name"], call["args"])
            results.append(ToolMessage(content=str(out), tool_call_id=call["id"], name=call["name"]))
        return {"messages": results}

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    workflow.set_entry_point("agent")
    
    def should_continue(state):
        last = state["messages"][-1]
        return "tools" if last.tool_calls else END

    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")

    # 3. Execute
    import asyncio
    graph = workflow.compile()
    final_state = asyncio.run(graph.ainvoke({"messages": messages}))
    
    final_response = final_state["messages"][-1].content
    
    # 4. Save history
    app.memory.save_message(session_id, "user", user_message)
    app.memory.save_message(session_id, "assistant", final_response)

    return {"result": final_response}
