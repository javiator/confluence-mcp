from bedrock_agentcore.runtime import BedrockAgentCoreApp
import logging

logging.basicConfig(level=logging.INFO)
app = BedrockAgentCoreApp()

print(f"App attributes: {dir(app)}")
try:
    print(f"App memory: {app.memory}")
except AttributeError:
    print("App has no 'memory' attribute")

try:
    print(f"App gateway: {app.gateway}")
except AttributeError:
    print("App has no 'gateway' attribute")
