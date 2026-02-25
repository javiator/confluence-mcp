# AgentCore AI Development Guide

> **ATTENTION AI AGENTS**: Read this document *before* modifying the Bedrock AgentCore runtime (`agentcore_runtime/src/main.py`). It contains critical architectural patterns and hard-won learnings that will prevent you from wasting hours debugging incorrect assumptions or hallucinating unsupported APIs.

## 1. Project Structure

This project is split into two distinct AWS components:
- **MCP Tool Server** (`src/mcp_server/`, `src/confluence_mcp/`): Deployed as a standalone AWS Lambda function. Do *not* put agent reasoning loop logic here.
- **AgentCore Runtime** (`agentcore_runtime/`): A hosted Docker container managed by Bedrock running the LangGraph orchestrator loop. It communicates with the MCP Lambda via an AgentCore Gateway.

## 2. Memory Persistence (CRITICAL)

**DO NOT use standard `MemorySessionManager` or custom `MemoryClient` classes to manage history in LangGraph.**

We use the official AWS Checkpointer for LangGraph: `langgraph-checkpoint-aws`.
The correct checkpointer class is `AgentCoreMemorySaver`.

**Crucial Configuration Rule**:
The `AgentCoreMemorySaver` will crash with `InvalidConfigError` unless you provide BOTH `thread_id` and `actor_id` in the `RunnableConfig`.

```python
from langgraph_checkpoint_aws import AgentCoreMemorySaver

checkpointer = AgentCoreMemorySaver(
    memory_id=os.environ.get("AGENTCORE_MEMORY_ID"),
    region_name=os.environ.get("AWS_REGION", "us-east-1")
)

# CRITICAL: Both thread_id and actor_id are mandatory!
config = {"configurable": {"thread_id": session_id, "actor_id": actor_id}}
async for event in graph.astream_events({"messages": [HumanMessage(content=user_message)]}, config, version="v2"):
    ...
```

## 3. Streaming and Event Handling

When streaming from Claude 3 models using `astream_events`, the chunks can be incoming as either plain strings OR lists of dictionary blocks. You MUST handle both formats to prevent `TypeError` crashes during the Server-Sent Events stream.

```python
if kind == "on_chat_model_stream":
    chunk = event["data"]["chunk"]
    content = getattr(chunk, "content", None)
    if isinstance(content, str) and content:
        yield content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                yield block.get("text", "")
```

**Fallback Required**: Always include fallback event captures for `on_chat_model_end` and `on_chain_end` to catch the final response. Sometimes the full response is delivered at the end rather than being perfectly yielded in `on_chat_model_stream` chunks.

## 4. MCP Gateway and Tool Naming

When connecting to the MCP Server through the AWS Bedrock AgentCore Gateway, the gateway automatically **prefixes all tool names**.

If your underlying MCP server exposes a tool named `search_confluence`, the AgentCore runtime will receive it as:
`confluence-mcp-lambda___search_confluence`

If you are writing or updating a `SYSTEM_PROMPT` to guide the agent on tool usage workflows, you **MUST** use the exact prefixed names, otherwise the LLM will hallucinate raw tool names that the LangGraph `ToolNode` will fail to route.

## 5. History Content Parsing (Bedrock Quirks)

If you ever need to manually inspect or parse history returned by Bedrock AgentCore Memory, note that the content might not be flat text. It can be a dict (`{"text": "..."}`) or a list of dicts. You must flatten it to strings before passing it into LangChain `HumanMessage` or `AIMessage` objects, or it will throw a Pydantic `ValidationError`. (This is largely solved by using `AgentCoreMemorySaver`, but applies to any custom parsing).

## 6. The MCP Connection

We use `mcp_proxy_for_aws.client.aws_iam_streamablehttp_client` to connect to the gateway.
Note that the standard `mcp_proxy_for_aws` library uses deprecation warnings around `streamable_http_client`. Ensure you use the exact imports currently established in `main.py` rather than attempting to rewrite the streaming HTTP transport layer.

## 7. Deployment and AWS Log Troubleshooting

When things go wrong in the hosted runtime (e.g., streaming crashes, memory failures, unhandled `ExceptionGroup`s), you DO NOT have local terminal output. You must use the `agentcore` CLI and AWS CloudWatch.

### A. Deploying Code Changes
The AgentCore runtime code (`src/main.py`) runs in a managed Docker container. Saving the file locally does nothing. You MUST deploy:
```bash
cd agentcore_runtime
agentcore deploy --env AGENTCORE_MEMORY_ID=confluence_memory-L0EwKGFITE
```
*(Wait the full ~2-3 minutes for the build to finish).*

### B. Finding the Exact Crash (The Observability CLI)
When an `invoke` fails, start here to find which span crashed:
```bash
agentcore obs list --session-id <your-session-id>
agentcore obs show --last 1  # or specify the trace-id
```
This tells you if it failed in `AgentCore.Runtime.Invoke` or elsewhere, and gives you a rough timestamp.

### C. Digging into CloudWatch Logs (The Real Tracebacks)
The `obs` command often swallows the deep Python tracebacks (like `InvalidConfigError`). To find the real exception, you must query CloudWatch.

**1. Tail recent logs:**
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/YOUR_AGENT_ID-DEFAULT --since 10m
```
*(Tip: Replace `YOUR_AGENT_ID` with the actual ID, e.g., `agentcoreconfluence_agent-TpNYJW6yK2`)*

**2. Find specific exception traces:**
If `tail` is too noisy, filter for the Python traceback:
```bash
aws logs filter-log-events \
  --log-group-name /aws/bedrock-agentcore/runtimes/YOUR_AGENT_ID-DEFAULT \
  --filter-pattern "Traceback" \
  --limit 50
```

**3. Exhaustive Stream Search:**
If you know a crash happened but can't see it in `tail`, you might be looking at the wrong log stream.
List all recent streams:
```bash
aws logs describe-log-streams \
  --log-group-name /aws/bedrock-agentcore/runtimes/YOUR_AGENT_ID-DEFAULT \
  --order-by LastEventTime \
  --descending \
  --limit 5
```
Then pull the exact events from the most recent stream:
```bash
aws logs get-log-events \
  --log-group-name /aws/bedrock-agentcore/runtimes/YOUR_AGENT_ID-DEFAULT \
  --log-stream-name "2026/02/25/[runtime-logs]..." \
  --limit 100
```

### D. The "ExceptionGroup" during Streaming
If you see an error like `unhandled errors in a TaskGroup (1 sub-exception) ... An error occurred during streaming`:
This means the LangGraph `astream_events` loop crashed and the AWS SDK wrapped the exception. **It is almost always a schema validation error (like flat strings vs lists in History) or an `AgentCoreMemorySaver` config error (missing `actor_id`).** Look at the CloudWatch logs immediately preceding the "ExceptionGroup" message to find the true cause.

