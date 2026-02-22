import boto3
import uuid

# Hardcoded ID from our Terraform deployment
AGENT_ID = "N2YKHR0RUU"
AGENT_ALIAS_ID = "TSTALIASID" # Default alias for DRAFT version
SESSION_ID = str(uuid.uuid4())

print(f"Connecting to AWS Bedrock Agent {AGENT_ID}...")
client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')

prompt = "Can you search Confluence for 'project alpha' and tell me what you find?"
print(f"\nPrompt: {prompt}\n")
print("Response: ", end="")

try:
    response = client.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=SESSION_ID,
        inputText=prompt
    )

    for event in response.get("completion"):
        if "chunk" in event:
            chunk = event["chunk"].get("bytes")
            if chunk:
                print(chunk.decode("utf-8"), end="", flush=True)
                
        elif "trace" in event:
            trace = event["trace"].get("trace", {})
            if "orchestrationTrace" in trace:
                orch = trace["orchestrationTrace"]
                if "invocationInput" in orch:
                    tool = orch["invocationInput"].get("actionGroupInvocationInput", {}).get("function")
                    if tool:
                        print(f"\n\n[System trace: Claude is calling tool -> {tool}]\n", end="")

    print("\n\nDone!")
except Exception as e:
    print(f"\nError invoking Bedrock Agent: {e}")
