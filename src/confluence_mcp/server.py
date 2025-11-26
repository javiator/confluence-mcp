import os
import json
import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from typing import List, Dict, Any, Optional

# Configuration
BASE_URL = os.environ.get("CONFLUENCE_BASE_URL", "").rstrip("/")
EMAIL = os.environ.get("CONFLUENCE_EMAIL", "")
API_TOKEN = os.environ.get("CONFLUENCE_API_TOKEN", "")

# Load Configuration
# Load Configuration
# Priority:
# 1. Environment Variable CONFLUENCE_MCP_CONFIG
# 2. config.json in Current Working Directory
# 3. config.json in Package Directory (fallback)

def load_config():
    # 1. Env Var
    env_config = os.environ.get("CONFLUENCE_MCP_CONFIG")
    if env_config and os.path.exists(env_config):
        try:
            with open(env_config, "r") as f:
                return json.load(f)
        except Exception:
            pass

    # 2. CWD
    cwd_config = os.path.join(os.getcwd(), "config.json")
    if os.path.exists(cwd_config):
        try:
            with open(cwd_config, "r") as f:
                return json.load(f)
        except Exception:
            pass
            
    # 3. Package Dir (Fallback)
    pkg_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(pkg_config):
        try:
            with open(pkg_config, "r") as f:
                return json.load(f)
        except Exception:
            pass

    # Default if no config found
    return {"allowed_spaces": [], "allowed_parents": {}}

config = load_config()
ALLOWED_SPACES = set(config.get("allowed_spaces", []))
# Convert lists to sets for faster lookup
ALLOWED_PARENTS = {k: set(v) for k, v in config.get("allowed_parents", {}).items()}

# Initialize FastMCP Server
mcp = FastMCP("Confluence MCP Server")

def get_auth():
    return (EMAIL, API_TOKEN)

def get_headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def clean_html(html_content: str) -> str:
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator="\n").strip()

@mcp.tool()
def search_confluence(query: str) -> List[Dict[str, Any]]:
    """
    Search for Confluence pages using CQL.
    Returns pages only from allowed spaces and within allowed parent hierarchies.
    If a parent page is specified in config, all its descendants are automatically allowed.
    """
    # Build base CQL query
    if "=" in query or " IN " in query.upper():
        # Assume raw CQL
        base_cql = f'({query}) AND type=page'
    else:
        # Simple text search
        base_cql = f'text~"{query}" AND type=page'
    
    # Build space filter
    if ALLOWED_SPACES:
        space_filter = " OR ".join([f'space = "{s}"' for s in ALLOWED_SPACES])
        base_cql = f'{base_cql} AND ({space_filter})'
    
    # Build ancestor filter for each space
    # This allows any page that is either:
    # 1. One of the allowed parent pages (id in (...))
    # 2. A descendant of an allowed parent page (ancestor in (...))
    ancestor_filters = []
    for space_key, parent_ids in ALLOWED_PARENTS.items():
        if parent_ids:
            parent_list = ", ".join(parent_ids)
            # Match pages that are either the parent itself OR have the parent as an ancestor
            space_ancestor_filter = f'(space = "{space_key}" AND (id in ({parent_list}) OR ancestor in ({parent_list})))'
            ancestor_filters.append(space_ancestor_filter)
    
    if ancestor_filters:
        ancestor_cql = " OR ".join(ancestor_filters)
        cql = f'{base_cql} AND ({ancestor_cql})'
    else:
        cql = base_cql
    
    url = f"{BASE_URL}/rest/api/search"
    
    try:
        response = requests.get(
            url,
            auth=get_auth(),
            params={"cql": cql, "limit": 50},
            headers=get_headers()
        )
        response.raise_for_status()
        data = response.json()
        
        results = []
        for result in data.get("results", []):
            # Extract space key
            space_key = None
            
            # Method 1: Try resultGlobalContainer
            container = result.get("resultGlobalContainer", {})
            display_url = container.get("displayUrl", "")
            if "/spaces/" in display_url:
                parts = display_url.split("/spaces/")
                if len(parts) > 1:
                    space_key = parts[1].split("/")[0]
            
            # Method 2: Try URL if Method 1 failed
            if not space_key:
                web_url = result.get("url", "")
                if "/spaces/" in web_url:
                    parts = web_url.split("/spaces/")
                    if len(parts) > 1:
                        space_key = parts[1].split("/")[0]
            
            # Method 3: Try content.space
            if not space_key:
                space_key = result.get("content", {}).get("space", {}).get("key")
                
            page_id = result.get("content", {}).get("id") or result.get("id")
            
            results.append({
                "id": str(page_id),
                "title": result.get("title"),
                "spaceKey": space_key,
                "url": f"{BASE_URL}{result.get('url', '')}",
                "excerpt": result.get("excerpt", "")
            })
            
        return results
    except requests.RequestException as e:
        raise RuntimeError(f"Error searching Confluence: {str(e)}")

@mcp.tool()
def get_confluence_page(page_id: str) -> Dict[str, Any]:
    """
    Get a Confluence page by ID, returning plain text content.
    """
    url = f"{BASE_URL}/rest/api/content/{page_id}"
    params = {"expand": "body.storage,space"}
    
    try:
        response = requests.get(
            url,
            auth=get_auth(),
            params=params,
            headers=get_headers()
        )
        response.raise_for_status()
        data = response.json()
        
        space_key = data.get("space", {}).get("key")
        body_html = data.get("body", {}).get("storage", {}).get("value", "")
        
        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "spaceKey": space_key,
            "url": f"{BASE_URL}{data.get('_links', {}).get('webui', '')}",
            "textContent": clean_html(body_html),
            "storageContent": body_html
        }
    except requests.RequestException as e:
        return {"error": str(e)}

@mcp.tool()
def create_confluence_page(space_key: str, parent_id: str, title: str, body: str) -> Dict[str, Any]:
    """
    Create a new Confluence page in a restricted set of spaces and parents.
    Automatically applies 'ai-generated' label.
    """
    # Access Control Checks
    if space_key not in ALLOWED_SPACES:
        return {"error": f"Space '{space_key}' is not in the allowed list."}
    
    allowed_parents = ALLOWED_PARENTS.get(space_key, set())
    if parent_id not in allowed_parents:
        return {"error": f"Parent ID '{parent_id}' is not allowed for space '{space_key}'."}

    url = f"{BASE_URL}/rest/api/content"
    payload = {
        "type": "page",
        "title": title,
        "ancestors": [{"id": parent_id}],
        "space": {"key": space_key},
        "body": {
            "storage": {
                "value": body,
                "representation": "storage"
            }
        },
        "metadata": {
            "labels": [
                {"prefix": "global", "name": "ai-managed"}
            ]
        }
    }
    
    try:
        response = requests.post(
            url,
            auth=get_auth(),
            json=payload,
            headers=get_headers()
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            "id": data.get("id"),
            "spaceKey": space_key,
            "url": f"{BASE_URL}{data.get('_links', {}).get('webui', '')}"
        }
    except requests.RequestException as e:
        return {"error": str(e)}

@mcp.tool()
def update_confluence_page_full(page_id: str, body: str) -> Dict[str, Any]:
    """
    Overwrite a Confluence page's body. 
    Only allowed if the page is in an allowed space and has 'ai-generated' or 'ai-managed' labels.
    """
    # 1. Fetch current info to check permissions and get version
    url_get = f"{BASE_URL}/rest/api/content/{page_id}"
    params = {"expand": "body.storage,space,version,metadata.labels"}
    
    try:
        response = requests.get(
            url_get,
            auth=get_auth(),
            params=params,
            headers=get_headers()
        )
        response.raise_for_status()
        current_data = response.json()
        
        # 2. Check permissions
        space_key = current_data.get("space", {}).get("key")
        if space_key not in ALLOWED_SPACES:
            return {"error": f"Page in space '{space_key}' cannot be modified (space not allowed)."}
        
        # Robust label extraction
        # The structure of labels might be different depending on expansion.
        labels_data = current_data.get("metadata", {}).get("labels", {}).get("results", [])
        
        # Fallback if it's a list directly
        if isinstance(current_data.get("metadata", {}).get("labels"), list):
             labels_data = current_data.get("metadata", {}).get("labels")
        
        labels = []
        for l in labels_data:
            if isinstance(l, dict):
                labels.append(l.get("name"))
            elif isinstance(l, str):
                labels.append(l)

        if "ai-generated" not in labels and "ai-managed" not in labels:
            return {"error": "Page does not have required 'ai-generated' or 'ai-managed' labels."}
            
        # 3. Prepare update payload
        current_version = current_data.get("version", {}).get("number", 1)
        current_title = current_data.get("title")
        
        payload = {
            "id": page_id,
            "type": "page",
            "title": current_title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body,
                    "representation": "storage"
                }
            },
            "version": {
                "number": current_version + 1
            }
        }
        
        # 4. Perform update
        url_put = f"{BASE_URL}/rest/api/content/{page_id}"
        response_put = requests.put(
            url_put,
            auth=get_auth(),
            json=payload,
            headers=get_headers()
        )
        response_put.raise_for_status()
        data = response_put.json()
        
        return {
            "id": data.get("id"),
            "spaceKey": space_key,
            "url": f"{BASE_URL}{data.get('_links', {}).get('webui', '')}"
        }
        
    except requests.RequestException as e:
        return {"error": str(e)}

@mcp.tool()
def prepare_confluence_page_merge_update(page_id: str) -> Dict[str, Any]:
    """
    Retrieve page content and metadata for merging. 
    Enforces the same access control as updates (allowed space + AI labels).
    """
    url = f"{BASE_URL}/rest/api/content/{page_id}"
    params = {"expand": "body.storage,space,version,metadata.labels"}
    
    try:
        response = requests.get(
            url,
            auth=get_auth(),
            params=params,
            headers=get_headers()
        )
        response.raise_for_status()
        data = response.json()
        
        # Check permissions
        space_key = data.get("space", {}).get("key")
        if space_key not in ALLOWED_SPACES:
            return {"error": f"Page in space '{space_key}' cannot be prepared for merge (space not allowed)."}
            
        labels = [l.get("name") for l in data.get("metadata", {}).get("labels", [])]
        if "ai-generated" not in labels and "ai-managed" not in labels:
            return {"error": "Page does not have required 'ai-generated' or 'ai-managed' labels."}
            
        body_html = data.get("body", {}).get("storage", {}).get("value", "")
        
        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "spaceKey": space_key,
            "url": f"{BASE_URL}{data.get('_links', {}).get('webui', '')}",
            "labels": labels,
            "version": data.get("version", {}).get("number"),
            "textContent": clean_html(body_html),
            "storageContent": body_html
        }
        
    except requests.RequestException as e:
        return {"error": str(e)}

@mcp.tool()
def get_confluence_children(page_id: str) -> List[Dict[str, Any]]:
    """
    Get direct child pages of a specific page.
    Useful for navigating the hierarchy when search is unreliable.
    """
    # 1. Verify access to the parent page first
    url_parent = f"{BASE_URL}/rest/api/content/{page_id}"
    try:
        response = requests.get(
            url_parent,
            auth=get_auth(),
            params={"expand": "ancestors,space"},
            headers=get_headers()
        )
        response.raise_for_status()
        parent_data = response.json()
        
        space_key = parent_data.get("space", {}).get("key")
        if space_key not in ALLOWED_SPACES:
             return [{"error": f"Space '{space_key}' not allowed"}]

        allowed_ids = ALLOWED_PARENTS.get(space_key, set())
        
        # Check if parent itself is allowed or is a descendant of an allowed page
        is_allowed = False
        if page_id in allowed_ids:
            is_allowed = True
        else:
            ancestors = parent_data.get("ancestors", [])
            ancestor_ids = {a.get("id") for a in ancestors}
            if ancestor_ids.intersection(allowed_ids):
                is_allowed = True
        
        if not is_allowed:
             return [{"error": "Parent page is not accessible under current permissions"}]

    except requests.RequestException as e:
        return [{"error": f"Error verifying parent page: {str(e)}"}]

    # 2. Fetch Children
    url_children = f"{BASE_URL}/rest/api/content/{page_id}/child/page"
    try:
        response = requests.get(
            url_children,
            auth=get_auth(),
            params={"limit": 50},
            headers=get_headers()
        )
        response.raise_for_status()
        data = response.json()
        
        results = []
        for result in data.get("results", []):
            results.append({
                "id": result.get("id"),
                "title": result.get("title"),
                "url": f"{BASE_URL}{result.get('_links', {}).get('webui', '')}"
            })
        return results
        
    except requests.RequestException as e:
        return [{"error": f"Error fetching children: {str(e)}"}]


