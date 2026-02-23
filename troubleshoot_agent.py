import boto3
import uuid
import json
import sys
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        return super().default(obj)

def troubleshoot_agent(input_text):
    agent_id = "M1SKX5WXKI"
    agent_alias_id = "TSTALIASID"
    session_id = str(uuid.uuid4())
    
    client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
    
    print(f"--- INVOKING AGENT: {input_text} ---")
    
    try:
        response = client.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            inputText=input_text,
            enableTrace=True
        )
        
        completion = ""
        for event in response.get("completion"):
            if "chunk" in event:
                chunk = event["chunk"]["bytes"].decode("utf-8")
                completion += chunk
                print(chunk, end="", flush=True)
            elif "trace" in event:
                trace = event["trace"]["trace"]
                if "orchestrationTrace" in trace:
                    orch = trace["orchestrationTrace"]
                    if "invocationInput" in orch:
                        print(f"\n[TRACE] Invocation Input: {json.dumps(orch['invocationInput'], indent=2, cls=DateTimeEncoder)}")
                    if "observation" in orch:
                        print(f"\n[TRACE] Observation: {json.dumps(orch['observation'], indent=2, cls=DateTimeEncoder)}")
                    if "rationale" in orch:
                        print(f"\n[TRACE] Rationale: {orch['rationale'].get('text')}")
        
        print("\n--- FINAL COMPLETION ---")
        print(completion)

    except Exception as e:
        print(f"\n--- ERROR CAUGHT ---")
        print(f"Type: {type(e)}")
        print(f"Message: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Full Response JSON: {json.dumps(e.response, indent=2, cls=DateTimeEncoder)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    query = "Search for pages related to google ai"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    troubleshoot_agent(query)
