import os
import json
import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from typing import List, Dict, Any, Optional, Annotated
from pydantic import Field
from dotenv import load_dotenv
import boto3
import html
from botocore.exceptions import ClientError

load_dotenv()

# In-memory cache for prepared page content (for Bedrock Agent workflow)
_prepared_pages_cache: Dict[str, Dict[str, Any]] = {}

def get_ssm_parameter(name: str) -> Optional[str]:
    """Fetch a parameter from AWS SSM Parameter Store if available."""
    try:
        ssm = boto3.client('ssm', region_name='us-east-1')
        response = ssm.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception:
        # Silently fail if not in AWS or parameter missing
        return None

# Configuration
# Priority: 1. Environment Variable 2. SSM Parameter Store
BASE_URL = (os.environ.get("CONFLUENCE_BASE_URL") or 
            get_ssm_parameter("/confluence/base_url") or 
            "").rstrip("/")
EMAIL = os.environ.get("CONFLUENCE_EMAIL") or get_ssm_parameter("/confluence/email") or ""
API_TOKEN = os.environ.get("CONFLUENCE_API_TOKEN") or get_ssm_parameter("/confluence/api_token") or ""

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

import re

def clean_html(html_content: str) -> str:
    """Extract plain text from Confluence storage XHTML."""
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove script and style elements
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        # Get text, using a newline as a separator for block elements
        text = soup.get_text(separator="\n")
        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    except Exception:
        return html_content # Fallback to raw if parsing fails




def robust_sanitize_confluence_xhtml(body: str) -> str:
    if not body:
        return body

    # Fix 0: Strip Confluence-generated 'invalidmacro' placeholders COMPLETELY
    body = re.sub(
        r'<ac:structured-macro ac:name="invalidmacro"[^>]*/>',
        '',
        body
    )
    body = re.sub(
        r'<ac:structured-macro ac:name="invalidmacro"[^>]*>.*?</ac:structured-macro>',
        '',
        body,
        flags=re.DOTALL
    )

    # Fix 0.5: Strip markdown code block indicators anywhere in the text
    body = re.sub(r'```[a-zA-Z]*\n?', '', body)
    body = re.sub(r'```', '', body)

    # Fix 0.6: Unescape entities if the model accidentally encoded the entire payload
    # This is a common failure mode for some LLMs.
    if "&lt;ac:" in body or "&lt;h1&gt;" in body or "&quot;" in body or "&lt;h2&gt;" in body:
        # Unescape up to 3 times to handle double/triple escaping if necessary
        for _ in range(3):
            if "&lt;" in body:
                body = html.unescape(body)
            else:
                break

    # Fix 0.7: Extract strictly from the first '<' to the last '>'
    # This automatically drops any conversational padding LLMs might hallucinate
    # around the actual HTML payload.
    start_idx = body.find('<')
    end_idx = body.rfind('>')
    if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
        body = body[start_idx:end_idx + 1]

    # Fix 0.75: Strip outer CDATA if the model wrapped the ENTIRE payload in it
    if body.startswith("<![CDATA[") and body.endswith("]]>"):
        body = body[9:-3].strip()

    # Fix 0.8: Ensure CDATA sections are closed within plain-text-body
    # Some LLMs start <![CDATA[ but forget ]]> OR they forget to close the tag entirely
    # before starting a new header or macro.
    
    # First, fix missing ]]> inside existing <ac:plain-text-body> tags
    def repair_cdata_closure(m):
        inner = m.group(1)
        if "<![CDATA[" in inner and "]]>" not in inner:
            return f"<ac:plain-text-body>{inner}]]></ac:plain-text-body>"
        return m.group(0)

    body = re.sub(
        r'<ac:plain-text-body>(.*?)</ac:plain-text-body>',
        repair_cdata_closure,
        body,
        flags=re.DOTALL
    )

    # Second, fix cases where <ac:plain-text-body> starts but NEVER closes
    # This happens when the model starts a code block and then just keeps going.
    # We find ALL <ac:plain-text-body> starts and ensure they don't swallow headers.
    
    def robust_dangling_repair(text):
        parts = re.split(r'(<ac:plain-text-body>)', text)
        new_parts = []
        for i in range(len(parts)):
            if parts[i] == '<ac:plain-text-body>':
                # The next part is the content of this body
                if i + 1 < len(parts):
                    content = parts[i+1]
                    # If this content doesn't have a closing tag but HAS a header/macro
                    if '</ac:plain-text-body>' not in content and ('<h' in content.lower() or '<ac:structured-macro' in content.lower()):
                         repair_point = re.search(r'(?i)<h[1-6]|<ac:', content)
                         if repair_point:
                             idx = repair_point.start()
                             pre = content[:idx]
                             post = content[idx:]
                             if "<![CDATA[" in pre and "]]>" not in pre:
                                 pre = pre + "]]>"
                             # Update the next part in the sequence
                             parts[i+1] = pre + "</ac:plain-text-body>\n" + post
                new_parts.append(parts[i])
            else:
                new_parts.append(parts[i])
        return "".join(new_parts)

    body = robust_dangling_repair(body)

    # Fix 1: <ac:parameter> missing ac:name
    body = re.sub(
        r'<ac:parameter>(.*?)</ac:parameter>',
        r'<ac:parameter ac:name="language">\1</ac:parameter>',
        body
    )

    # Fix 2: <ac:structured-macro> missing ac:name
    def repair_macro_callback(match):
        start_tag = match.group(1)
        inner_content = match.group(2)
        end_tag = match.group(3)
        
        # If it already has ac:name, leave it as is
        if 'ac:name=' in start_tag:
            return match.group(0)
            
        # Guess name based on inner body tag
        if '<ac:plain-text-body' in inner_content:
            new_start = start_tag.replace('<ac:structured-macro', '<ac:structured-macro ac:name="code"')
        elif '<ac:rich-text-body' in inner_content:
            new_start = start_tag.replace('<ac:structured-macro', '<ac:structured-macro ac:name="info"')
        else:
            new_start = start_tag.replace('<ac:structured-macro', '<ac:structured-macro ac:name="info"')
            
        return f"{new_start}{inner_content}{end_tag}"

    # Match <ac:structured-macro ...> ... </ac:structured-macro>
    # Using a slightly safer non-iterative approach that targets tags without ac:name
    body = re.sub(
        r'(<ac:structured-macro(?![^>]*ac:name=)[^>]*>)(.*?)(</ac:structured-macro>)',
        repair_macro_callback,
        body,
        flags=re.DOTALL
    )

    return body


@mcp.tool()
def search_confluence(query: str) -> List[Dict[str, Any]]:
    return _search_confluence(query)

def _search_confluence(query: str) -> List[Dict[str, Any]]:
    """
    Search for Confluence pages using CQL.
    Returns pages only from allowed spaces and within allowed parent hierarchies.
    If a parent page is specified in config, all its descendants are automatically allowed.
    """
    # Build base CQL query
    # Check if the query looks like raw CQL (contains explicit operators and is not just a title)
    cql_operators = ["=", "~", " IN ", " OR ", " AND "]
    is_raw_cql = any(op in query or op.upper() in query.upper() for op in cql_operators)
    
    # If it's a multi-word query but lacks explicit '=' or '~', assume it's a search term
    # Titles like "How to Install and Uninstall Docker on Ubuntu" contain AND but aren't CQL.
    # We force text search if no explicit property operator (~, =) is found.
    if is_raw_cql and ("=" in query or "~" in query or " IN " in query.upper()):
        base_cql = f'({query}) AND type=page'
    else:
        # Simple text search - escape quotes and wrap in text search
        safe_query = query.replace('"', '\\"')
        base_cql = f'text ~ "{safe_query}" AND type=page'
    
    # Build space filter
    if ALLOWED_SPACES:
        space_filter = " OR ".join([f'space = "{s}"' for s in ALLOWED_SPACES])
        base_cql = f'({base_cql}) AND ({space_filter})'
    
    # Build ancestor filter for each space
    ancestor_filters = []
    for space_key, parent_ids in ALLOWED_PARENTS.items():
        if parent_ids:
            parent_list = ", ".join([f'"{pid}"' for pid in parent_ids])
            # Match pages that are either the parent itself OR have the parent as an ancestor
            space_ancestor_filter = f'(space = "{space_key}" AND (id in ({parent_list}) OR ancestor in ({parent_list})))'
            ancestor_filters.append(space_ancestor_filter)
    
    if ancestor_filters:
        ancestor_cql = " OR ".join(ancestor_filters)
        cql = f'({base_cql}) AND ({ancestor_cql})'
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
    return _get_confluence_page(page_id)

def _get_confluence_page(page_id: str) -> Dict[str, Any]:
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
def execute_confluence_publish(
    space_key: str, 
    parent_id: str, 
    title: str, 
    xhtml_payload: Annotated[str, Field(description="MANDATORY: The full Confluence XHTML content to publish.")]
) -> Dict[str, Any]:
    """
    Create a new Confluence page with mandatory XHTML content.
    Requires space_key, parent_id, title, AND xhtml_payload.
    """
    if not xhtml_payload:
         return {"error": "Missing required argument 'xhtml_payload'. You MUST provide the page content."}
    
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
                "value": robust_sanitize_confluence_xhtml(xhtml_payload),
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
def update_page_full(page_id: str, page_content_xhtml: str = "") -> Dict[str, Any]:
    """
    Update a Confluence page with a new full page_content_xhtml payload.
    Requires page_id AND page_content_xhtml.
    """
    if not page_content_xhtml:
        return {"error": "Missing required argument 'page_content_xhtml'. You MUST provide the fully merged XHTML string."}
    merged_body = page_content_xhtml

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
                    "value": robust_sanitize_confluence_xhtml(merged_body),
                    "representation": "storage"
                }
            },
            "version": {
                "number": current_version + 1
            },
            "metadata": {
                "labels": [{"prefix": "global", "name": l} for l in labels]
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
def append_to_page(page_id: str, page_content_xhtml: str = "") -> Dict[str, Any]:
    """
    Append new content to the bottom of an existing Confluence page.
    Requires page_id AND page_content_xhtml.
    """
    if not page_content_xhtml:
        return {"error": "Missing required argument 'page_content_xhtml'. You MUST provide the content to append."}
    url_get = f"{BASE_URL}/rest/api/content/{page_id}"
    params = {"expand": "body.storage,space,version,metadata.labels"}

    try:
        response = requests.get(url_get, auth=get_auth(), params=params, headers=get_headers())
        response.raise_for_status()
        data = response.json()

        space_key = data.get("space", {}).get("key")
        if space_key not in ALLOWED_SPACES:
            return {"error": f"Space '{space_key}' is not in the allowed list."}

        labels_data = data.get("metadata", {}).get("labels", {}).get("results", [])
        if isinstance(data.get("metadata", {}).get("labels"), list):
            labels_data = data.get("metadata", {}).get("labels")

        labels = []
        for l in labels_data:
            if isinstance(l, dict):
                labels.append(l.get("name"))
            elif isinstance(l, str):
                labels.append(l)

        if "ai-generated" not in labels and "ai-managed" not in labels:
            return {"error": "Page does not have required 'ai-generated' or 'ai-managed' labels."}

        current_version = data.get("version", {}).get("number", 1)
        current_title = data.get("title")
        current_body = data.get("body", {}).get("storage", {}).get("value", "")

        # Sanitize and merge
        sanitized_new = robust_sanitize_confluence_xhtml(body)
        merged_body = current_body + "\n" + sanitized_new

        payload = {
            "id": page_id,
            "type": "page",
            "title": current_title,
            "space": {"key": space_key},
            "body": {"storage": {"value": merged_body, "representation": "storage"}},
            "version": {"number": current_version + 1},
            "metadata": {"labels": [{"prefix": "global", "name": l} for l in labels]}
        }

        url_put = f"{BASE_URL}/rest/api/content/{page_id}"
        resp_put = requests.put(url_put, auth=get_auth(), json=payload, headers=get_headers())
        resp_put.raise_for_status()
        result = resp_put.json()

        return {
            "id": result.get("id"),
            "message": "Content appended successfully!",
            "url": f"{BASE_URL}{result.get('_links', {}).get('webui', '')}"
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
            
        # Robust label extraction
        labels_data = data.get("metadata", {}).get("labels", {}).get("results", [])
        if isinstance(data.get("metadata", {}).get("labels"), list):
             labels_data = data.get("metadata", {}).get("labels")
             
        labels = []
        for l in labels_data:
            if isinstance(l, dict):
                labels.append(l.get("name"))
            elif isinstance(l, str):
                labels.append(l)

        if "ai-generated" not in labels and "ai-managed" not in labels:
            return {"error": "Page does not have required 'ai-generated' or 'ai-managed' labels."}
            
        body_html = data.get("body", {}).get("storage", {}).get("value", "")
        # Sanitize the content we return to the agent to remove "zombie" errors
        sanitized_body = robust_sanitize_confluence_xhtml(body_html)

        # Cache the full content server-side to avoid passing large XML between tool calls
        _prepared_pages_cache[page_id] = {
            "id": data.get("id"),
            "title": data.get("title"),
            "spaceKey": space_key,
            "url": f"{BASE_URL}{data.get('_links', {}).get('webui', '')}",
            "labels": labels,
            "version": data.get("version", {}).get("number"),
            "storageContent": sanitized_body
        }

        # Return metadata AND text context to the agent so it can perform the merge logic
        return {
            "status": "prepared",
            "page_id": page_id,
            "title": data.get("title"),
            "version": data.get("version", {}).get("number"),
            "existingContent": clean_html(body_html),
            "message": f"Page {page_id} prepared for update. Existing content provided in 'existingContent'. Use this to generate your new merged XHTML and call update_confluence_page_full."
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


