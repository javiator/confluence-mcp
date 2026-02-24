# AgentCore Migration Guide

This document covers every manual AWS step needed to move from the current
local setup to a fully cloud-hosted architecture.

## Architecture overview

```
Chainlit (local)
  └─▶ AWS Bedrock AgentCore  (hosted agent + ReAct loop)
        └─▶ AgentCore Gateway  (MCP protocol proxy)
              └─▶ Lambda: ConfluenceAgentCoreMCP  (NEW — dedicated to AgentCore)
                    └─▶ Confluence REST API
```

## What this does NOT touch

The following resources from the legacy 4-agent Bedrock Agents system are
left completely untouched by everything in this guide:

| Resource | Used by |
|---|---|
| `ConfluenceMCPServer` Lambda | Legacy Bedrock Agents (HTTP MCP experiment) |
| `ConfluenceTools` Lambda | Legacy Bedrock Agents action groups |
| 4× `aws_bedrockagent_agent` resources | Supervisor / Search / Writer / Reviewer agents |
| ECR repo `confluence-mcp-server` | ConfluenceMCPServer image |

The new AgentCore setup lives entirely in `terraform/agentcore_mcp/` with its
own ECR repo, Lambda, IAM role, and Function URL.

---

## Step 1 — Deploy the new Terraform resources

```bash
cd terraform/agentcore_mcp

terraform init
terraform apply
```

This creates:
- ECR repository: `confluence-agentcore-mcp`
- Lambda function: `ConfluenceAgentCoreMCP`
- IAM role: `ConfluenceAgentCoreMCPRole`
- Lambda Function URL (IAM auth)

Note the two output values — you will need them in the steps below:
```
agentcore_mcp_ecr_url        = "123456789.dkr.ecr.us-east-1.amazonaws.com/confluence-agentcore-mcp"
agentcore_mcp_function_url   = "https://xxxx.lambda-url.us-east-1.on.aws/"
agentcore_mcp_lambda_arn     = "arn:aws:lambda:us-east-1:123456789:function:ConfluenceAgentCoreMCP"
```

---

## Step 2 — Build and push the AgentCore Docker image

Use `Dockerfile.agentcore` (not the main `Dockerfile`) so the legacy Lambda
is never touched.

```bash
# Run from the repo root
ECR_URL=$(terraform -chdir=terraform/agentcore_mcp output -raw agentcore_mcp_ecr_url)

# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "$ECR_URL"

# Build using the AgentCore-specific Dockerfile
docker build -f Dockerfile.agentcore -t confluence-agentcore-mcp .

# Tag and push
docker tag confluence-agentcore-mcp:latest "$ECR_URL:latest"
docker push "$ECR_URL:latest"

# Update the Lambda to use the new image
aws lambda update-function-code \
  --function-name ConfluenceAgentCoreMCP \
  --image-uri "$ECR_URL:latest" \
  --region us-east-1
```

Wait ~30 seconds, then verify:
```bash
aws lambda get-function \
  --function-name ConfluenceAgentCoreMCP \
  --query 'Configuration.LastUpdateStatus' \
  --output text
# Expected: Successful
```

---

## Step 3 — Verify the Lambda MCP endpoint

The Function URL has IAM auth, so use `awscurl` for local testing
(`pip install awscurl`):

```bash
LAMBDA_URL=$(terraform -chdir=terraform/agentcore_mcp output -raw agentcore_mcp_function_url)

# tools/list — should return 7 tools
awscurl --service lambda --region us-east-1 \
  -X POST "${LAMBDA_URL}mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Expected: 7 tools —
`search_confluence`, `get_confluence_page`, `get_confluence_children`,
`execute_confluence_publish`, `update_page_full`, `append_to_page`,
`prepare_confluence_page_merge_update`.

---

## Step 4 — Create the AgentCore Gateway

The Gateway is what connects AgentCore to your Lambda using the MCP protocol.

### 4a. Open the AWS Console

1. **Amazon Bedrock** → left sidebar → **AgentCore** → **Gateway**
2. Click **Create gateway**

### 4b. Configure the gateway

| Field | Value |
|---|---|
| Name | `confluence-agentcore-gateway` |
| Protocol | **MCP** |
| Endpoint URL | `<agentcore_mcp_function_url>mcp` (append `/mcp` to the Terraform output) |
| Auth type | **IAM** |

### 4c. IAM role for the Gateway

Create a new IAM role for the Gateway with this inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunctionUrl",
      "Resource": "<agentcore_mcp_lambda_arn>"
    }
  ]
}
```

The Lambda resource policy (`AllowAgentCoreGatewayInvoke`) was already added
by Terraform in Step 1.

### 4d. Save the Gateway ARN

After creation, copy the **Gateway ARN** — you need it in Step 5.

---

## Step 5 — Create the AgentCore agent

### 5a. Open AgentCore agents

1. **Amazon Bedrock** → **AgentCore** → **Agent runtimes**
2. Click **Create agent runtime**

### 5b. Basic settings

| Field | Value |
|---|---|
| Name | `confluence-agent` |
| Foundation model | `anthropic.claude-3-5-sonnet-20241022-v2:0` (or latest Sonnet) |

### 5c. System prompt

Copy the `SYSTEM_PROMPT` constant from
`src/confluence_mcp/agent/bedrock_graph.py` into the **Instructions** field.
It starts with:

> *"You are an expert Confluence Assistant..."*

### 5d. Connect the Gateway

Under **Tools** or **MCP connections**:
1. Click **Add tool source**
2. Select **AgentCore Gateway**
3. Choose `confluence-agentcore-gateway` (created in Step 4)
4. The agent will discover all 7 tools automatically via `tools/list`

### 5e. Create an alias

1. Click **Create**
2. Once status shows **Prepared**, click **Create alias**
3. Alias name: `live`
4. Copy the **Agent ID** and **Alias ID**

---

## Step 6 — Update your local `.env`

```bash
USE_AGENTCORE=true
AGENTCORE_AGENT_ID=<Agent ID from Step 5e>
AGENTCORE_AGENT_ALIAS_ID=<Alias ID from Step 5e>
```

---

## Step 7 — Test end-to-end

```bash
uv run chainlit run src/confluence_mcp/agent/app.py
```

Send: *"Search for pages about Docker in space ENG"*

You should see:
- No local MCP subprocess starts
- Response comes from AgentCore via Lambda → Confluence
- The legacy Bedrock Agents system is completely unaffected

---

## Switching back to local mode

```bash
USE_AGENTCORE=false
```

The app falls back to `bedrock_graph.py` + local stdio MCP — exactly as before.

---

## Resource inventory

| Resource name | File | Notes |
|---|---|---|
| ECR: `confluence-agentcore-mcp` | `terraform/agentcore_mcp/main.tf` | New |
| Lambda: `ConfluenceAgentCoreMCP` | `terraform/agentcore_mcp/main.tf` | New |
| Docker image | `Dockerfile.agentcore` | New — does NOT affect main `Dockerfile` |
| MCP server code | `agentcore_server.py` | New — does NOT affect `fastapi_server.py` |
| AgentCore Gateway | AWS Console (Step 4) | New |
| AgentCore agent | AWS Console (Step 5) | New |
| ECR: `confluence-mcp-server` | `terraform/managed/mcp_server.tf` | **Unchanged** |
| Lambda: `ConfluenceMCPServer` | `terraform/managed/mcp_server.tf` | **Unchanged** |
| Lambda: `ConfluenceTools` | `terraform/managed/main.tf` | **Unchanged** |
| 4× Bedrock Agents | `terraform/managed/main.tf` | **Unchanged** |

---

## Troubleshooting

| Symptom | Check |
|---|---|
| `AGENTCORE_AGENT_ID is not set` in Chainlit | Add to `.env` and restart |
| Gateway returns 403 | IAM Gateway role missing `lambda:InvokeFunctionUrl` permission |
| `tools/list` returns 0 tools | Lambda image not pushed — repeat Step 2 |
| Agent responds but ignores tools | System prompt missing — verify Step 5c |
| Lambda cold-start timeout | Increase `timeout` in `terraform/agentcore_mcp/main.tf` and re-apply |
