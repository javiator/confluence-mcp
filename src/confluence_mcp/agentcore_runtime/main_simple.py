"""
Simple AgentCore Runtime agent for testing deployment.

This is a minimal working agent to verify the deployment pipeline works.
Once this works, we'll add LangGraph + Gateway integration.
"""

import logging
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simple-agent")

app = BedrockAgentCoreApp()

SYSTEM_PROMPT = """You are an expert Confluence Assistant.
Your primary job is to SEARCH for pages and PUBLISH new content.

CRITICAL OPERATIONAL RULES:
1. SILENT TOOL CALLS: DO NOT speak, acknowledge, or explain before calling a tool.
2. MANDATORY PAYLOAD: The argument for XHTML content is 'xhtml_payload' for creation.
3. NEVER OMIT the payload. It is required for the tool to function.

STABILIZED WORKFLOW:
- SEARCH: search_confluence(query="...")
- CREATE: execute_confluence_publish(space_key="...", parent_id="...", title="...", xhtml_payload="...")
"""


@app.entrypoint
def invoke(payload):
    """
    AgentCore Runtime entrypoint.

    For now, this is a simple echo agent to verify deployment works.
    Next step: Add LangGraph + Gateway integration.
    """
    user_message = payload.get("prompt", "Hello")
    session_id = payload.get("sessionId", "default")
    
    logger.info(f"Received message: '{user_message}' for session: {session_id}")

    # Simple response for testing
    response = f"Received: {user_message}\n\nAgent is running successfully in AgentCore Runtime!"

    logger.info(f"Sending response: '{response}'")
    return {"result": response}


if __name__ == "__main__":
    app.run()
