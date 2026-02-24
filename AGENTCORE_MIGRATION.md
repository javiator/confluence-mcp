# AgentCore Migration Guide

This document covers every manual AWS step needed to move from the current
local setup to a fully cloud-hosted architecture:

```
Chainlit (local)
  └─▶ AWS Bedrock AgentCore  (hosted agent + ReAct loop)
        └─▶ AgentCore Gateway  (MCP protocol proxy)
              └─▶ Lambda: ConfluenceMCPServer  (HTTP MCP server)
                    └─▶ Confluence REST API
```

Prerequisites: AWS CLI configured, Docker installed, ECR/Lambda already
created by Terraform (see `terraform/managed/`).

---

## Step 1 — Rebuild and deploy the Lambda MCP server

The Docker image has been updated (`fastapi_server.py` now exposes the correct
tool names and the full MCP protocol).  Push the new image and update Lambda.

```bash
# 1a. Get the ECR repo URL
ECR_URL=$(aws ecr describe-repositories \
  --repository-names confluence-mcp-server \
  --query 'repositories[0].repositoryUri' \
  --output text)

echo "ECR URL: $ECR_URL"

# 1b. Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "$ECR_URL"

# 1c. Build the image (run from the repo root)
docker build -t confluence-mcp-server .

# 1d. Tag and push
docker tag confluence-mcp-server:latest "$ECR_URL:latest"
docker push "$ECR_URL:latest"

# 1e. Update the Lambda function
aws lambda update-function-code \
  --function-name ConfluenceMCPServer \
  --image-uri "$ECR_URL:latest" \
  --region us-east-1
```

Wait ~30 seconds for the update to propagate, then verify:

```bash
aws lambda get-function \
  --function-name ConfluenceMCPServer \
  --query 'Configuration.LastUpdateStatus' \
  --output text
# Expected: Successful
```

---

## Step 2 — Smoke-test the Lambda MCP endpoint

Get the Lambda Function URL (already created by Terraform):

```bash
LAMBDA_URL=$(aws lambda get-function-url-config \
  --function-name ConfluenceMCPServer \
  --query 'FunctionUrl' \
  --output text)

echo "Lambda URL: $LAMBDA_URL"
```

Test the three MCP methods.  You will need to sign requests with AWS SigV4
because the Function URL has `authorization_type = "AWS_IAM"`.  The easiest
way is to use the AWS CLI with `--payload` and a Bedrock-aware caller, or
temporarily switch auth to `NONE` for testing:

```bash
# Quick test without IAM auth (only if you temporarily set auth=NONE):
curl -s -X POST "${LAMBDA_URL}mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | jq .

curl -s -X POST "${LAMBDA_URL}mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | jq .
```

Expected `tools/list` response — 7 tools:
`search_confluence`, `get_confluence_page`, `get_confluence_children`,
`execute_confluence_publish`, `update_page_full`, `append_to_page`,
`prepare_confluence_page_merge_update`.

> **Tip**: For a proper SigV4-signed test from your local machine, use
> `awscurl` (`pip install awscurl`) or the AWS SDK:
> ```bash
> awscurl --service lambda --region us-east-1 \
>   -X POST "${LAMBDA_URL}mcp" \
>   -H "Content-Type: application/json" \
>   -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
> ```

---

## Step 3 — Create the AgentCore Gateway

The Gateway is what connects AgentCore to your Lambda MCP server using the
MCP protocol.

### 3a. Open the AWS Console

1. Go to **Amazon Bedrock** → left sidebar → **AgentCore** → **Gateway**
2. Click **Create gateway**

### 3b. Configure the gateway

| Field | Value |
|---|---|
| Name | `confluence-mcp-gateway` |
| Protocol | **MCP** |
| Endpoint URL | Your Lambda Function URL + `/mcp` (e.g. `https://xxxx.lambda-url.us-east-1.on.aws/mcp`) |
| Auth type | **IAM** |

### 3c. IAM permissions

The Gateway needs permission to invoke the Lambda Function URL.
Create or reuse an IAM role for the Gateway and attach:

```json
{
  "Effect": "Allow",
  "Action": "lambda:InvokeFunctionUrl",
  "Resource": "<ConfluenceMCPServer Lambda ARN>"
}
```

Also update the Lambda resource policy to allow the Gateway principal:

```bash
aws lambda add-permission \
  --function-name ConfluenceMCPServer \
  --statement-id AllowAgentCoreGateway \
  --action lambda:InvokeFunctionUrl \
  --principal bedrock-agentcore.amazonaws.com \
  --function-url-auth-type AWS_IAM \
  --region us-east-1
```

### 3d. Save the Gateway ARN

After creation, copy the Gateway ARN — you will need it in Step 4.

---

## Step 4 — Create the AgentCore agent

### 4a. Open AgentCore agents

1. **Amazon Bedrock** → **AgentCore** → **Agent runtimes**
2. Click **Create agent runtime**

### 4b. Basic settings

| Field | Value |
|---|---|
| Name | `confluence-agent` |
| Foundation model | `anthropic.claude-3-5-sonnet-20241022-v2:0` (or latest Sonnet) |
| Description | Single-agent Confluence assistant |

### 4c. System prompt

Copy the exact system prompt from `bedrock_graph.py` (`SYSTEM_PROMPT` constant)
into the **Instructions** field.  It starts with:

> *"You are an expert Confluence Assistant..."*

### 4d. Tools / MCP Gateway

Under the **Tools** or **MCP connections** section:

1. Click **Add tool source**
2. Select **AgentCore Gateway**
3. Choose the `confluence-mcp-gateway` you created in Step 3
4. The agent will automatically discover all 7 tools via `tools/list`

### 4e. Create and prepare

1. Click **Create**
2. Once status is **Prepared**, click **Create alias**
3. Set alias name: `live`
4. Copy both the **Agent ID** and **Alias ID**

---

## Step 5 — Update your local `.env`

```bash
# In your .env file (copy .env.example if you haven't already):
USE_AGENTCORE=true
AGENTCORE_AGENT_ID=<paste Agent ID from Step 4e>
AGENTCORE_AGENT_ALIAS_ID=<paste Alias ID from Step 4e>
```

Leave all other values (`CONFLUENCE_*`, AWS credentials) as they are.

---

## Step 6 — Test end-to-end

Start Chainlit as usual:

```bash
uv run chainlit run src/confluence_mcp/agent/app.py
```

Send a test message:

> *"Search for pages about Docker in space ENG"*

You should see:
- No local MCP subprocess starts up
- Chainlit displays the response from the AgentCore agent
- The agent called `search_confluence` via the Lambda through the Gateway

---

## Switching back to local mode

Set `USE_AGENTCORE=false` in `.env` (or remove the variable).  The app falls
back to `bedrock_graph.py` + local stdio MCP, exactly as it worked before.

---

## Architecture diagram

```
Your laptop
  ├── Chainlit UI (app.py)
  │     │  USE_AGENTCORE=true
  │     ▼
  │  boto3 bedrock-agent-runtime.invoke_agent()
  │     │
  └─────┼─────────────────────────────────────────▶ AWS
        │
        ▼
  AgentCore Agent Runtime
    system prompt: SYSTEM_PROMPT from bedrock_graph.py
    model: Claude Sonnet (via Bedrock)
    ReAct loop: managed by AgentCore
        │
        │ MCP tool calls
        ▼
  AgentCore Gateway
    protocol: MCP over HTTPS
    auth: IAM SigV4
        │
        ▼
  Lambda: ConfluenceMCPServer
    runtime: fastapi_server.py (Docker / Lambda Web Adapter)
    tools: 7 MCP tools
        │
        ▼
  Confluence REST API
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| `AGENTCORE_AGENT_ID is not set` error in Chainlit | Add `AGENTCORE_AGENT_ID` to `.env` and restart |
| Gateway returns 403 | Lambda resource policy missing `AllowAgentCoreGateway` — re-run Step 3d |
| `tools/list` returns 0 tools | Lambda image not updated — repeat Step 1 |
| Agent responds but doesn't call tools | System prompt missing — verify Step 4c |
| Lambda cold-start timeout | Increase Lambda timeout in Terraform (`timeout = 120`) and redeploy |
| `append_to_page` was broken locally | Fixed: `body` → `page_content_xhtml` bug in `server.py` is resolved |
