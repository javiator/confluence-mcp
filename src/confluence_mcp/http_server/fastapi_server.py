import logging
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# We import these after load_dotenv because they read os.environ on initialization
from confluence_mcp.server import (
    _search_confluence, 
    _get_confluence_page, 
    create_confluence_page, 
    update_confluence_page_full, 
    prepare_confluence_page_merge_update, 
    get_confluence_children
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("confluence-mcp-http")

# Create the FastAPI app for Streamable HTTP
app = FastAPI(title="Confluence MCP Server (HTTP)")

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    Stateless JSON-RPC processing endpoint.
    Bypasses the strict MCP 'initialize' handshake since AWS Lambda is stateless.
    """
    try:
        body_bytes = await request.body()
        req_data = json.loads(body_bytes)
        
        logger.info(f"Received JSON-RPC request: {req_data}")
        
        if req_data.get("method") == "tools/call":
            params = req_data.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            
            output_text = ""
            
            try:
                if name == "search_confluence":
                    query = arguments.get("query")
                    if not query:
                        raise ValueError("Missing 'query' parameter")
                    
                    results = _search_confluence(query=query)
                    
                    for item in results:
                        if "error" in item:
                            output_text += f"Error: {item['error']}\n"
                            continue
                        output_text += f"ID: {item.get('id')}\n"
                        output_text += f"Title: {item.get('title')}\n"
                        output_text += f"Space: {item.get('spaceKey')}\n"
                        output_text += f"URL: {item.get('url')}\n"
                        output_text += f"Excerpt: {item.get('excerpt', 'No excerpt')}\n"
                        output_text += "-" * 40 + "\n"
                    
                    if not output_text:
                        output_text = "No results found for query."

                elif name == "get_confluence_page":
                    page_id = arguments.get("page_id")
                    if not page_id:
                        raise ValueError("Missing 'page_id' parameter")
                    
                    page = _get_confluence_page(page_id=page_id)
                    
                    if "error" in page:
                         output_text = f"Error: {page['error']}"
                    else:
                        title = page.get("title", "Unknown Title")
                        body = page.get("textContent", "")
                        output_text = f"Title: {title}\nID: {page_id}\nURL: {page.get('url')}\n\nContent:\n{body}"
                elif name == "create_confluence_page":
                    res = create_confluence_page(
                        space_key=arguments.get("space_key"),
                        parent_id=arguments.get("parent_id"),
                        title=arguments.get("title"),
                        body=arguments.get("body")
                    )
                    if "error" in res:
                        output_text = f"Error: {res['error']}"
                    else:
                        output_text = f"Page created successfully!\nID: {res.get('id')}\nURL: {res.get('url')}"

                elif name == "update_confluence_page_full":
                    res = update_confluence_page_full(
                        page_id=arguments.get("page_id"),
                        body=arguments.get("body")
                    )
                    if "error" in res:
                        output_text = f"Error: {res['error']}"
                    else:
                        output_text = f"Page updated successfully!\nID: {res.get('id')}\nURL: {res.get('url')}"

                elif name == "prepare_confluence_page_merge_update":
                    res = prepare_confluence_page_merge_update(
                        page_id=arguments.get("page_id")
                    )
                    if "error" in res:
                        output_text = f"Error: {res['error']}"
                    else:
                        output_text = f"Page Preparation Data:\nTitle: {res.get('title')}\nVersion: {res.get('version')}\n\nCurrent Content:\n{res.get('storageContent')}"

                elif name == "get_confluence_children":
                    page_id = arguments.get("page_id")
                    results = get_confluence_children(page_id=page_id)
                    for item in results:
                        if "error" in item:
                            output_text += f"Error: {item['error']}\n"
                            continue
                        output_text += f"ID: {item.get('id')}\n"
                        output_text += f"Title: {item.get('title')}\n"
                        output_text += f"URL: {item.get('url')}\n"
                        output_text += "-" * 40 + "\n"
                    if not output_text:
                        output_text = "No children found."

                else:
                    output_text = f"Error: Unknown tool {name}"
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                output_text = f"Error executing tool {name}: {str(e)}"
            
            # Format the successful JSON-RPC response
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": req_data.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": output_text
                        }
                    ]
                }
            })
            
        else:
            return JSONResponse(content={"jsonrpc": "2.0", "id": req_data.get("id"), "error": {"code": -32601, "message": "Method not found"}})
            
    except Exception as e:
        logger.error(f"Failed to process MCP message: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Confluence MCP Server on http://0.0.0.0:8000/mcp")
    uvicorn.run(app, host="0.0.0.0", port=8000)
