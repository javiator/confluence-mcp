# AgentCore Runtime Agent

This directory contains the Python agent code for AWS Bedrock AgentCore Runtime deployment.

## Structure

- `main.py` - Agent handler with system prompt
- `requirements.txt` - Python dependencies
- `deploy.sh` - Script to package and upload to S3

## Deployment

1. Package the agent:
```bash
cd src/confluence_mcp/agentcore_runtime
zip -r agent.zip main.py requirements.txt
```

2. Upload to S3:
```bash
aws s3 cp agent.zip s3://bedrock-agentcore-runtime-383226947124-us-east-1-vv5aiw1cye/confluence_agent/
```

3. Deploy via AWS Console:
   - Go to: Bedrock → AgentCore → Host agent or tool
   - Source: S3 bucket
   - Choose the uploaded agent.zip
   - Entry point: `main.py`
   - Handler: `handler`

## How it Works

The agent is a simple pass-through that:
1. Receives user input from AgentCore
2. Returns the system prompt for Confluence operations
3. AgentCore handles model invocation and tool calling via the Gateway
4. Gateway connects to the ConfluenceAgentCoreMCP Lambda (MCP server)
