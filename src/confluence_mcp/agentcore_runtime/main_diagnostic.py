from bedrock_agentcore.runtime import BedrockAgentCoreApp
import logging
import json

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    prompt = payload.get("prompt", "")
    return {"result": f"Diagnostic response (SDK included) to: {prompt}"}
