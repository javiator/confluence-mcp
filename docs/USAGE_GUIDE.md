# Usage & Deployment Guide

This guide covers how to deploy the Confluence MCP AgentCore application from scratch, how to use it day-to-day, helpful CLI commands, and how to tear it all down when you're done.

## 🚀 1. Deploying from Scratch

If you are starting fresh in a new AWS Account or Region, follow these steps:

### A. Deploy the MCP Tool Server (Terraform)
The MCP server runs as a standalone AWS Lambda function that provides Confluence tools securely to Bedrock.

```bash
cd terraform/agentcore_mcp
terraform init
terraform apply
```
*Note the output `agentcore_mcp_function_url`.*

### B. Build and Push the MCP Server Image
```bash
# From the repository root
./scripts/deploy_agentcore_mcp.sh
```
*This script automatically fetches the ECR URL from Terraform, builds `Dockerfile`, and updates the Lambda.*

### C. Deploy the Hosted AgentCore Logic
The logic, memory, and orchestration run as a natively hosted AWS Bedrock AgentCore container.

> [!IMPORTANT]
> **Working with the `agentcore` CLI**
> The `agentcore` CLI reads its configuration from a `.bedrock_agentcore.yaml` file. This file only exists inside `src/confluence_mcp/agentcore_runtime/docker_agent/agentcoreconfluence/`. You **must** be inside this specific directory whenever you run any `agentcore` commands, otherwise it will fail with a `Configuration not found` error.

```bash
cd agentcore_runtime
# Deploy to AWS Bedrock
agentcore deploy --env BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0 --env AGENTCORE_MEMORY_ID=your-memory-id
```

### D. Connect the Agent to the MCP Server
1. Open the **AWS Console** -> **Amazon Bedrock** -> **AgentCore**.
2. Create an **AgentCore Gateway**:
   - Protocol: `MCP`
   - Endpoint: Your `agentcore_mcp_function_url` + `mcp` (e.g., `https://.../mcp`)
   - Auth: `IAM`
3. Link the Gateway to your newly deployed Agent under its **Tools/Connections** settings.

---

## 💻 2. Daily Usage

### Starting the UI
To chat with your hosted agent using the Chainlit web UI:

1. Ensure your `.env` is configured:
   ```env
   USE_AGENTCORE=true
   AGENTCORE_AGENT_ID=arn:aws:bedrock-agentcore:us-east-1:123456789:runtime/your-agent-id
   AGENTCORE_MEMORY_ID=your-memory-id
   ```
2. Launch the server:
   ```bash
   ./start_agent.sh
   ```
3. Open `http://localhost:8000` in your browser.

---

## 🛠️ 3. Helpful AgentCore Commands

The `agentcore` CLI is your debug companion for the hosted Bedrock runtime.

> [!WARNING]
> Remember: You **must** run these commands from the directory containing the `.bedrock_agentcore.yaml` config file:
> `cd agentcore_runtime`

**View Agent Status:**
```bash
agentcore status
```

**Stream Live Logs:**
```bash
agentcore logs -f
```

**Invoke Headless (No UI):**
```bash
agentcore invoke '{"prompt": "Search Confluence for Docker setup"}'
```

**Update Environment Variables/Model:**
```bash
agentcore deploy --env BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

---

## 🗑️ 4. Tearing Down (Removal)

If you are done and want to stop incurring any AWS costs, you must destroy the infrastructure in reverse order.

### A. Delete the Hosted AgentCore Application
```bash
cd agentcore_runtime
agentcore delete
```
*Wait for this to complete. It removes the Bedrock configuration and CodeBuild projects.*

### B. Delete the AgentCore Gateway
1. Go to the **AWS Bedrock Console** -> **AgentCore** -> **Gateways**.
2. Select your gateway and click **Delete**.

### C. Destroy the MCP Server (Terraform)
```bash
cd terraform/agentcore_mcp
terraform destroy -auto-approve
```
*This removes the Lambda, IAM roles, and ECR repository.*
