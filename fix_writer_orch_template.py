#!/usr/bin/env python3
"""Fix Writer Agent ORCHESTRATION template and set max_length=4096"""
import boto3
import json

client = boto3.client('bedrock-agent', region_name='us-east-1')

# Get correct ORCHESTRATION template from Search Agent
search_resp = client.get_agent(agentId='HMUJPTSXHZ')
search_configs = search_resp['agent']['promptOverrideConfiguration']['promptConfigurations']
search_orch = [c for c in search_configs if c['promptType'] == 'ORCHESTRATION'][0]
correct_template = search_orch['basePromptTemplate']

# Get Writer Agent current config
writer_resp = client.get_agent(agentId='M1SKX5WXKI')
writer = writer_resp['agent']

print("--- Fixing Writer Agent ORCHESTRATION template and maximumLength ---")

update_params = {
    'agentId': 'M1SKX5WXKI',
    'agentName': writer['agentName'],
    'agentResourceRoleArn': writer['agentResourceRoleArn'],
    'foundationModel': writer['foundationModel'],
    'instruction': writer['instruction'],
    'promptOverrideConfiguration': {
        'promptConfigurations': [
            {
                'promptType': 'ORCHESTRATION',
                'promptCreationMode': 'OVERRIDDEN',
                'promptState': 'ENABLED',
                'basePromptTemplate': correct_template,
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
    print("✓ Writer Agent ORCHESTRATION updated successfully")

    orch_config = update_resp['agent']['promptOverrideConfiguration']['promptConfigurations'][0]
    print(f"\nNew ORCHESTRATION config:")
    print(f"  promptCreationMode: {orch_config['promptCreationMode']}")
    print(f"  maximumLength: {orch_config['inferenceConfiguration']['maximumLength']}")
    print(f"  Template (first 300 chars): {orch_config['basePromptTemplate'][:300]}")

except Exception as e:
    print(f"✗ Error: {e}")
    raise
