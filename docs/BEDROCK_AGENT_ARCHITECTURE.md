# Bedrock AgentCore: Cloud-Native Architecture

This guide describes the high-performance, cloud-native architecture of the Confluence MCP agent using AWS Bedrock AgentCore.

---

## 🧭 The Big Picture

```
You (Chainlit)
    │
    ▼
┌──────────────────┐       ┌────────────────────────┐
│  Local UI        │──────▶│  AWS Bedrock AgentCore │
│  (app.py)        │◀──────│  (Hosted Logic + Mem)  │
└──────────────────┘       └────────────────────────┘
                                      │ (MCP over HTTPS)
                                      ▼
                           ┌────────────────────────┐
                           │  AgentCore Gateway     │
                           │  (Secure MCP Proxy)    │
                           └────────────────────────┘
                                      │
                                      ▼
                           ┌────────────────────────┐
                           │  AWS Lambda            │
                           │  (MCP Tool Server)     │
                           └────────────────────────┘
                                      │
                                      ▼
                           ┌────────────────────────┐
                           │  Confluence REST API   │
                           └────────────────────────┘
```

The system uses a **hosted runtime** model. Unlike local agents where the loop runs on your machine, the entire thinking process, tool selection, and conversation memory happen natively inside AWS Bedrock.

### Key Advantages
- **Managed Memory**: Session history is handled by Bedrock, persisting across frontend restarts.
- **Serverless Scaling**: The orchestrator and the tools are fully serverless (AgentCore + Lambda).
- **Security**: IAM-based authentication secures every hop from the Gateway to the Lambda.

---

## 🛠️ Core Components

### 1. `server.py` — The MCP Provider
Containerized in AWS Lambda, this provides the actual Confluence logic. It handles the nuances of the Confluence API, including:
- **XHTML Sanitization**: Fixing common LLM formatting errors in Confluence Storage Format.
- **Access Control**: Enforcing `config.json` filters for spaces and parent pages.

### 2. Bedrock AgentCore — The Orchestrator
The "brain" that receives user prompts from the UI. It uses the **AgentCore Gateway** to discover and execute tools in the Lambda function. It maintains the "ReAct" loop (Think → Act → Observe) autonomously.

### 3. Chainlit UI — The Interface
A lightweight frontend (`app.py`) that simply passes messages to Bedrock and displays the streamed responses. It supports both local runs and remote deployments (e.g., via AWS App Runner).

---

## 🔗 Setup & Deep Dive
- For manual setup steps and troubleshooting, see **[AGENTCORE_SETUP.md](./AGENTCORE_SETUP.md)**.
- For a history of the project phases, see **[PHASE_TRACKER.md](../PHASE_TRACKER.md)**.
