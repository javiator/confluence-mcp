import json
import logging
import os
import urllib.request
import urllib.error
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from urllib.parse import urlparse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# The Target Lambda Function for the Cloud-Native MCP Server
MCP_FUNCTION_NAME = "ConfluenceMCPServer"

def forward_to_mcp(action_group, function, parameters):
    """
    Forwards the action group request to the MCP server running in another Lambda.
    """
    mcp_request = {
        "jsonrpc": "2.0",
        "id": "bedrock-invoke",
        "method": "tools/call",
        "params": {
            "name": function,
            "arguments": parameters
        }
    }
    
    logger.info(f"Forwarding to Native MCP Lambda {MCP_FUNCTION_NAME}: {mcp_request}")
    
    client = boto3.client('lambda')
    
    # We construct a standard Lambda Payload Format 2.0 event that the Lambda Web Adapter understands
    payload = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/mcp",
        "rawQueryString": "",
        "headers": {
            "content-type": "application/json"
        },
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/mcp",
                "protocol": "HTTP/1.1"
            }
        },
        "body": json.dumps(mcp_request),
        "isBase64Encoded": False
    }
    
    try:
        response = client.invoke(
            FunctionName=MCP_FUNCTION_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        response_data = response['Payload'].read().decode('utf-8')
        logger.info(f"Raw response from MCP Lambda: {response_data}")
        
        response_payload = json.loads(response_data)
        
        # Lambda Proxy responses have 'statusCode' and 'body'
        if response_payload.get('statusCode') == 200:
            mcp_response = json.loads(response_payload['body'])
            logger.info(f"Successfully received response body: {mcp_response}")
            
            # The MCP Server returns a JSON-RPC response
            if "error" in mcp_response:
                return {"error": mcp_response["error"]}
                
            # Extract the actual text content returned by the tool
            content_blocks = mcp_response.get("result", {}).get("content", [])
            if content_blocks:
                return content_blocks[0].get("text", "No text returned by tool")
            return "Execution successful but no content returned."
        else:
            logger.error(f"MCP Server returned error status {response_payload.get('statusCode')}: {response_payload}")
            return f"Error: MCP Server returned status {response_payload.get('statusCode')}"
            
    except Exception as e:
        logger.error(f"Error invoking MCP Lambda: {str(e)}")
        return f"Error: {str(e)}"

def handler(event, context):
    """Handle tool calls from Bedrock Agent"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    action_group = event.get('actionGroup')
    function = event.get('function')
    parameters = event.get('parameters', [])

    # Convert parameters from Bedrock's name/value format to a flat dictionary
    params_dict = {p['name']: p['value'] for p in parameters}

    # Forward the request to your local laptop
    result = forward_to_mcp(action_group, function, params_dict)

    # Format response expected by Bedrock Agent
    response_body = {
        'TEXT': {
            # Bedrock expects pure string content here
            'body': result if isinstance(result, str) else json.dumps(result)
        }
    }

    return {
        'response': {
            'actionGroup': action_group,
            'function': function,
            'functionResponse': {
                'responseBody': response_body
            }
        }
    }
