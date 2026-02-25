# AWS Bedrock AgentCore Setup Guide

This guide covers the manual AWS configuration steps and troubleshooting for the hosted Bedrock AgentCore runtime.

## 🧭 Architecture overview

```
Chainlit (local/remote)
  └─▶ AWS Bedrock AgentCore (hosted logic + memory)
        └─▶ AgentCore Gateway (secure MCP proxy)
              └─▶ Lambda: ConfluenceAgentCoreMCP
                    └─▶ Confluence API
```

## 🛠️ Initial Setup

### 1. Infrastructure (Terraform)
Run the Terraform stack to create ECR, Lambda, and IAM roles:
```bash
cd terraform/agentcore_mcp
terraform init
terraform apply
```

### 2. Bedrock Configuration

#### Gateway Setup
1. **Bedrock Console** → **AgentCore** → **Gateway** → **Create**.
2. **Protocol**: MCP.
3. **Endpoint**: Your Lambda Function URL + `/mcp`.
4. **Auth**: IAM.

#### Agent Runtime
1. **Bedrock Console** → **AgentCore** → **Agent runtimes** → **Create**.
2. **Model**: Claude 3.5 Sonnet or Claude 3 Haiku.
3. **Gateway**: Connect the gateway created above.
4. **Alias**: Create an alias (e.g., `live`) and note the **Agent ID** and **Alias ID**.

## 🔧 Troubleshooting

| Symptom | Check |
|---|---|
| `AGENTCORE_AGENT_ID not set` | Add to `.env` and restart Chainlit. |
| Gateway 403 Forbidden | Ensure Gateway IAM role has `lambda:InvokeFunctionUrl`. |
| 0 tools discovered | Verify Lambda image is pushed and `/mcp` path is correct. |
| Logic/Prompt ignores tools | Ensure the system prompt includes tool-use instructions. |
| Lambda Timeouts | Increase Lambda timeout in Terraform or check for cold starts. |

## 📦 Resource Inventory
- **ECR**: `confluence-agentcore-mcp` (hosted image)
- **Lambda**: `ConfluenceAgentCoreMCP` (tool executor)
- **Gateway**: `confluence-agentcore-gateway` (MCP bridge)
- **Agent**: `confluence-agent` (orchestrator)
