import boto3
import time
import json

def prepare_and_version():
    client = boto3.client('bedrock-agent', region_name='us-east-1')
    
    agent_info = [
        {"id": "HMUJPTSXHZ", "alias_id": "LRCPLKP7QR", "name": "search-alias"},
        {"id": "M1SKX5WXKI", "alias_id": "XN7Q0IVSHR", "name": "writer-alias"},
        {"id": "CEXKSDYGIG", "alias_id": "XVRG1JV6YW", "name": "reviewer-alias"},
        {"id": "WRRZLA5LTA", "alias_id": "TSTALIASID", "name": "AgentTestAlias"}
    ]
    
    for agent in agent_info:
        agent_id = agent["id"]
        alias_id = agent["alias_id"]
        alias_name = agent["name"]
        
        print(f"--- Processing Agent: {agent_id} ---")
        
        # 1. Prepare
        print("Preparing agent...")
        client.prepare_agent(agentId=agent_id)
        
        # 2. Wait for Prepared
        while True:
            resp = client.get_agent(agentId=agent_id)
            status = resp["agent"]["agentStatus"]
            if status == "PREPARED":
                break
            print(f"Still preparing (status: {status})...")
            time.sleep(2)
        
        # 3. Create Version
        print("Creating version...")
        try:
            v_resp = client.create_agent_version(agentId=agent_id)
        except AttributeError:
            print("Falling back to low-level _make_api_call for CreateAgentVersion...")
            v_resp = client._make_api_call('CreateAgentVersion', {'agentId': agent_id})
        
        version = v_resp["agentVersion"]["version"]
        print(f"New Version: {version}")
        
        # 4. Update Alias
        # We need to wait a tiny bit for the version to be available for the alias
        time.sleep(1)
        print(f"Updating alias {alias_id} to version {version}...")
        client.update_agent_alias(
            agentId = agent_id,
            agentAliasId = alias_id,
            agentAliasName = alias_name,
            routingConfiguration = [{"agentVersion": version}]
        )
        print("Alias updated successfully.")

if __name__ == "__main__":
    prepare_and_version()
