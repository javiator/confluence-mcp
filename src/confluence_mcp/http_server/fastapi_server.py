import logging
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# Import after load_dotenv so env vars are available during server.py initialization
from confluence_mcp.server import (
    _search_confluence,
    _get_confluence_page,
    execute_confluence_publish,
    update_page_full,
    append_to_page,
    prepare_confluence_page_merge_update,
    get_confluence_children,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("confluence-mcp-http")

app = FastAPI(title="Confluence MCP Server (HTTP)")

# ── Tool catalogue ────────────────────────────────────────────────────────────
# Mirrors the @mcp.tool() definitions in server.py exactly.
# AgentCore Gateway reads this list via tools/list to understand what the
# MCP server can do.

TOOLS = [
    {
        "name": "search_confluence",
        "description": (
            "Search Confluence for pages using keywords or a CQL expression. "
            "Returns page IDs, titles, space keys, URLs, and excerpts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keywords or a CQL expression (e.g. 'Docker Ubuntu' or 'space=\"ENG\" AND text~\"deploy\"')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_confluence_page",
        "description": (
            "Fetch a Confluence page by ID. "
            "Returns the page title, URL, plain-text content, and raw storage XHTML."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The numeric ID of the Confluence page"
                }
            },
            "required": ["page_id"]
        }
    },
    {
        "name": "get_confluence_children",
        "description": "List the direct child pages of a given Confluence page.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The numeric ID of the parent page"
                }
            },
            "required": ["page_id"]
        }
    },
    {
        "name": "execute_confluence_publish",
        "description": (
            "Create a new Confluence page. "
            "All four arguments are mandatory. "
            "The xhtml_payload must be fully-formed Confluence storage XHTML — no markdown, no placeholders."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "space_key": {
                    "type": "string",
                    "description": "Key of the Confluence space (e.g. 'ENG', 'AR')"
                },
                "parent_id": {
                    "type": "string",
                    "description": "Numeric ID of the parent page"
                },
                "title": {
                    "type": "string",
                    "description": "Title for the new page"
                },
                "xhtml_payload": {
                    "type": "string",
                    "description": "MANDATORY: Full Confluence storage XHTML content for the page body"
                }
            },
            "required": ["space_key", "parent_id", "title", "xhtml_payload"]
        }
    },
    {
        "name": "update_page_full",
        "description": (
            "Replace the full content of an existing Confluence page. "
            "The page must carry an 'ai-generated' or 'ai-managed' label. "
            "page_content_xhtml must be complete Confluence storage XHTML."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "Numeric ID of the page to update"
                },
                "page_content_xhtml": {
                    "type": "string",
                    "description": "MANDATORY: The complete new Confluence storage XHTML content"
                }
            },
            "required": ["page_id", "page_content_xhtml"]
        }
    },
    {
        "name": "append_to_page",
        "description": (
            "Append new content to the bottom of an existing Confluence page without replacing anything. "
            "The page must carry an 'ai-generated' or 'ai-managed' label."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "Numeric ID of the page to append to"
                },
                "page_content_xhtml": {
                    "type": "string",
                    "description": "MANDATORY: Confluence storage XHTML content to append"
                }
            },
            "required": ["page_id", "page_content_xhtml"]
        }
    },
    {
        "name": "prepare_confluence_page_merge_update",
        "description": (
            "Retrieve the current content and version of a page to prepare for a merge update. "
            "Call this before update_page_full when you need to merge new content with existing content. "
            "Returns the existing plain-text content so the agent can compose the merged XHTML."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "Numeric ID of the page to prepare"
                }
            },
            "required": ["page_id"]
        }
    },
]

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    Stateless JSON-RPC MCP endpoint consumed by AgentCore Gateway.

    Handles the three methods the MCP protocol requires:
      - initialize   : capability handshake
      - tools/list   : return the tool catalogue
      - tools/call   : execute a specific tool
    """
    try:
        body_bytes = await request.body()
        req_data = json.loads(body_bytes)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON: {e}"})

    method = req_data.get("method")
    req_id = req_data.get("id")
    logger.info(f"MCP request: method={method}")

    # ── initialize ────────────────────────────────────────────────────────────
    if method == "initialize":
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "confluence-mcp", "version": "1.0.0"}
            }
        })

    # ── tools/list ────────────────────────────────────────────────────────────
    elif method == "tools/list":
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS}
        })

    # ── tools/call ────────────────────────────────────────────────────────────
    elif method == "tools/call":
        params = req_data.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})
        output_text = ""

        try:
            if name == "search_confluence":
                query = arguments.get("query")
                if not query:
                    raise ValueError("Missing required argument 'query'")
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
                    output_text = "No results found."

            elif name == "get_confluence_page":
                page_id = arguments.get("page_id")
                if not page_id:
                    raise ValueError("Missing required argument 'page_id'")
                page = _get_confluence_page(page_id=page_id)
                if "error" in page:
                    output_text = f"Error: {page['error']}"
                else:
                    output_text = (
                        f"Title: {page.get('title')}\n"
                        f"ID: {page_id}\n"
                        f"URL: {page.get('url')}\n\n"
                        f"Content:\n{page.get('textContent', '')}"
                    )

            elif name == "get_confluence_children":
                page_id = arguments.get("page_id")
                if not page_id:
                    raise ValueError("Missing required argument 'page_id'")
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

            elif name == "execute_confluence_publish":
                res = execute_confluence_publish(
                    space_key=arguments.get("space_key"),
                    parent_id=arguments.get("parent_id"),
                    title=arguments.get("title"),
                    xhtml_payload=arguments.get("xhtml_payload", ""),
                )
                if "error" in res:
                    output_text = f"Error: {res['error']}"
                else:
                    output_text = f"Page created!\nID: {res.get('id')}\nURL: {res.get('url')}"

            elif name == "update_page_full":
                res = update_page_full(
                    page_id=arguments.get("page_id"),
                    page_content_xhtml=arguments.get("page_content_xhtml", ""),
                )
                if "error" in res:
                    output_text = f"Error: {res['error']}"
                else:
                    output_text = f"Page updated!\nID: {res.get('id')}\nURL: {res.get('url')}"

            elif name == "append_to_page":
                res = append_to_page(
                    page_id=arguments.get("page_id"),
                    page_content_xhtml=arguments.get("page_content_xhtml", ""),
                )
                if "error" in res:
                    output_text = f"Error: {res['error']}"
                else:
                    output_text = f"Content appended!\nID: {res.get('id')}\nURL: {res.get('url')}"

            elif name == "prepare_confluence_page_merge_update":
                res = prepare_confluence_page_merge_update(
                    page_id=arguments.get("page_id"),
                )
                if "error" in res:
                    output_text = f"Error: {res['error']}"
                else:
                    output_text = (
                        f"Status: {res.get('status')}\n"
                        f"Title: {res.get('title')}\n"
                        f"Version: {res.get('version')}\n\n"
                        f"Existing Content:\n{res.get('existingContent', '')}"
                    )

            else:
                output_text = f"Error: Unknown tool '{name}'"

        except Exception as e:
            import traceback
            traceback.print_exc()
            output_text = f"Error executing tool '{name}': {str(e)}"

        return JSONResponse(content={
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": output_text}]
            }
        })

    # ── unknown method ────────────────────────────────────────────────────────
    else:
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        })


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Confluence MCP Server on http://0.0.0.0:8000/mcp")
    uvicorn.run(app, host="0.0.0.0", port=8000)
