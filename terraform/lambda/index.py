import json
import logging
import os
import urllib.request
import urllib.error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# The Cloudflare URL will be provided via an environment variable assigned by Terraform
CLOUDFLARE_URL = os.environ.get("CLOUDFLARE_URL", "http://localhost:8000")

def forward_to_mcp(action_group, function, parameters):
    """
    Forward the Bedrock Action Group request to the local Streamable HTTP MCP Server
    via the Cloudflare tunnel.
    """
    # 1. Format the request into a standard JSON-RPC HTTP Payload expected by the MCP HTTP Transport
    # Note: Streamable HTTP standard defines taking JSON-RPC directly in the body
    mcp_request = {
        "jsonrpc": "2.0",
        "id": "bedrock-invoke",
        "method": "tools/call",
        "params": {
            "name": function,
            "arguments": parameters
        }
    }
    
    req_body = json.dumps(mcp_request).encode('utf-8')
    url = f"{CLOUDFLARE_URL}/mcp"
    
    logger.info(f"Forwarding to MCP Server at {url}: {mcp_request}")
    
    req = urllib.request.Request(
        url,
        data=req_body,
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            resp_body = response.read().decode('utf-8')
            logger.info(f"Received from MCP Server: {resp_body}")
            
            # The MCP Server returns a JSON-RPC response
            # Format: {"jsonrpc": "2.0", "id": "bedrock-invoke", "result": {"content": [{"type": "text", "text": "..."}]}}
            mcp_response = json.loads(resp_body)
            
            if "error" in mcp_response:
                return {"error": mcp_response["error"]}
                
            # Extract the actual text content returned by the tool
            content_blocks = mcp_response.get("result", {}).get("content", [])
            if content_blocks:
                return content_blocks[0].get("text", "No text returned by tool")
            return "Execution successful but no content returned."
            
    except urllib.error.URLError as e:
        logger.error(f"HTTP Error querying MCP Server: {e}")
        return {"error": f"Failed to connect to local MCP Server: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": str(e)}

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
