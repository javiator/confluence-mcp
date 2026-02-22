import boto3
import json

def test_search():
    client = boto3.client('lambda', region_name='us-east-1')
    
    payload = {
        "actionGroup": "search-actions",
        "function": "search_confluence",
        "parameters": [
            {"name": "query", "type": "string", "value": "docker"}
        ],
        "sessionId": "debug-search"
    }
    
    print("Invoking search_confluence via Lambda...")
    response = client.invoke(
        FunctionName='ConfluenceTools',
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    
    result = json.loads(response['Payload'].read())
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test_search()
