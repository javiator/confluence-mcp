import os
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from mcp import ClientSession
from langchain_mcp_adapters.tools import load_mcp_tools

# Confluence MCP Gateway endpoint
CONFLUENCE_GATEWAY_URL = os.environ.get(
    "CONFLUENCE_GATEWAY_URL",
    "https://confluence-agentcore-gateway-pejofakb0g.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
)

async def get_mcp_tools_from_gateway():
    """
    Connects to AgentCore Gateway using AWS IAM SigV4 authentication and returns MCP tools.
    Uses mcp-proxy-for-aws to automatically sign requests with Runtime's IAM role credentials.
    """
    aws_region = os.environ.get("AWS_REGION", "us-east-1")

    # Create AWS IAM authenticated MCP client for bedrock-agentcore service
    mcp_client = aws_iam_streamablehttp_client(
        endpoint=CONFLUENCE_GATEWAY_URL,
        aws_region=aws_region,
        aws_service="bedrock-agentcore"
    )

    # Establish session and load tools
    async with mcp_client as (read, write, session_id_callback):
        async with ClientSession(read, write) as session:
            # Initialize the MCP session
            await session.initialize()
            # Load tools for LangChain/LangGraph
            tools = await load_mcp_tools(session)
            return tools