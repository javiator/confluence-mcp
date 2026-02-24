from bedrock_agentcore.runtime import BedrockAgentCoreApp
import logging

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    prompt = payload.get("prompt", "")
    return {"result": f"Ultra-minimal response to: {prompt}"}
