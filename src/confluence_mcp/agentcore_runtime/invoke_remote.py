import boto3
import json
import argparse
import sys

def invoke_agent(prompt, session_id="default-session"):
    # Target ARN found via aws bedrock-agentcore-control list-agent-runtimes
    AGENT_RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:383226947124:runtime/hosted_agent_t61xh-LRcuKXEkqy"
    
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")
    
    payload = {
        "prompt": prompt,
        "sessionId": session_id
    }
    
    print(f"invoking agent with prompt: {prompt}")
    
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            contentType="application/json",
            accept="application/json",
            payload=json.dumps(payload).encode("utf-8")
        )
        
        # response["response"] is a streaming body
        body = response["response"].read().decode("utf-8")
        result = json.loads(body)
        
        print("\n--- Agent Response ---")
        print(result.get("result", "No result found in response"))
        print("----------------------")
        
    except Exception as e:
        print(f"Error invoking agent: {e}")
        if hasattr(e, "response"):
            print(f"Detailed error: {e.response}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Invoke Bedrock AgentCore Agent remotely")
    parser.add_argument("prompt", help="User prompt for the agent")
    parser.add_argument("--session", default="test-session-python", help="Session ID")
    
    args = parser.parse_args()
    
    invoke_agent(args.prompt, args.session)
