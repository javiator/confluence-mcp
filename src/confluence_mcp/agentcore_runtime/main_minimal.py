from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    print(f"DEBUG: payload received: {payload}")
    return {"result": "Minimal agent response"}

# if __name__ == "__main__":
#     app.run()
