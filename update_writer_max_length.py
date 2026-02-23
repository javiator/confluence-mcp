#!/usr/bin/env python3
"""Update Writer Agent to increase max_length from 2048 to 4096"""
import boto3
import json

client = boto3.client('bedrock-agent', region_name='us-east-1')
agent_id = "M1SKX5WXKI"

# Get current agent config
resp = client.get_agent(agentId=agent_id)
agent = resp['agent']

print("Current agent configuration:")
print(f"  Name: {agent['agentName']}")
print(f"  Status: {agent['agentStatus']}")

# Check current prompt override
if 'promptOverrideConfiguration' in agent:
    print("\nCurrent promptOverrideConfiguration:")
    print(json.dumps(agent['promptOverrideConfiguration'], indent=2))
else:
    print("\nNo promptOverrideConfiguration currently set")

# Update with new max_length
print("\n--- Updating agent with max_length=4096 for ORCHESTRATION ---")

update_params = {
    'agentId': agent_id,
    'agentName': agent['agentName'],
    'agentResourceRoleArn': agent['agentResourceRoleArn'],
    'foundationModel': agent['foundationModel'],
    'instruction': agent['instruction'],
    'promptOverrideConfiguration': {
        'promptConfigurations': [
            {
                'promptType': 'ORCHESTRATION',
                'promptCreationMode': 'OVERRIDDEN',
                'promptState': 'ENABLED',
                'basePromptTemplate': [c for c in agent['promptOverrideConfiguration']['promptConfigurations'] if c['promptType'] == 'ORCHESTRATION'][0]['basePromptTemplate'],
                'inferenceConfiguration': {
                    'maximumLength': 4096,
                    'temperature': 0.0,
                    'topP': 1.0,
                    'topK': 250,
                    'stopSequences': ['</invoke>', '</answer>', '</error>']
                },
                'parserMode': 'DEFAULT'
            }
        ]
    }
}

try:
    update_resp = client.update_agent(**update_params)
    print("✓ Agent updated successfully")

    if 'promptOverrideConfiguration' in update_resp['agent']:
        print("\nNew promptOverrideConfiguration:")
        print(json.dumps(update_resp['agent']['promptOverrideConfiguration'], indent=2))

except Exception as e:
    print(f"✗ Error: {e}")
    raise
