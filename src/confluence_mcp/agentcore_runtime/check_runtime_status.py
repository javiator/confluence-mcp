import boto3

client = boto3.client("bedrock-agentcore", region_name="us-east-1")
try:
    response = client.get_agent_runtime(agentRuntimeId="hosted_agent_t61xh-LRcuKXEkqy")
    print(f"Version: {response['agentRuntimeVersion']}, Status: {response['status']}")
except Exception as e:
    print(f"Error: {e}")
