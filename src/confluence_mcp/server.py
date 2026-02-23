import os
import json
import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import boto3
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

def convert_wiki_markup_to_xhtml(body: str) -> str:
    """
    Convert Confluence Wiki Markup to storage format XHTML.
    Handles common patterns: h1-h6 headings, code blocks, lists.
    """
    if not body:
        return body

    # Strip outer <p> tags if they're wrapping Wiki markup
    stripped = body.strip()
    if stripped.startswith('<p>') and stripped.endswith('</p>'):
        inner = stripped[3:-4]  # Remove <p> and </p>
        # Check if inner content looks like Wiki markup
        if re.match(r'^h[1-6]\.', inner.strip()) or '{code' in inner:
            body = inner

    # Check if it's already proper XHTML (has proper heading or ac: tags)
    if '<h1>' in body or '<h2>' in body or '<ac:' in body:
        return body

    lines = body.split('\n')
    output = []
    in_code_block = False
    code_lang = None
    code_content = []

    for line in lines:
        # Code block end: {code} - check this FIRST before checking for start
        if in_code_block and line.strip() == '{code}':
            in_code_block = False
            # Build proper XHTML code macro with CDATA
            code_str = '\n'.join(code_content)
            code_xml = f'<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">{code_lang}</ac:parameter><ac:plain-text-body><![CDATA[{code_str}]]></ac:plain-text-body></ac:structured-macro>'
            output.append(code_xml)
            continue

        # Code block start: {code:lang} or {code}
        if line.strip().startswith('{code'):
            in_code_block = True
            # Extract language if specified
            match = re.match(r'\{code:(\w+)\}', line.strip())
            code_lang = match.group(1) if match else 'none'
            code_content = []
            continue

        if in_code_block:
            code_content.append(line)
            continue

        # Headings: h1. h2. h3. etc
        heading_match = re.match(r'^h([1-6])\.\s+(.+)$', line.strip())
        if heading_match:
            level = heading_match.group(1)
            text = heading_match.group(2)
            output.append(f'<h{level}>{text}</h{level}>')
            continue

        # Bullet list: * item
        if line.strip().startswith('* '):
            text = line.strip()[2:]
            output.append(f'<ul><li>{text}</li></ul>')
            continue

        # Numbered list: # item
        if line.strip().startswith('# '):
            text = line.strip()[2:]
            output.append(f'<ol><li>{text}</li></ol>')
            continue

        # Plain paragraph
        if line.strip():
            output.append(f'<p>{line.strip()}</p>')

    return ''.join(output)


def robust_sanitize_confluence_xhtml(body: str) -> str:
    if not body:
        return body

    # First, try to convert Wiki markup to XHTML if needed
    body = convert_wiki_markup_to_xhtml(body)

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

    # Fix 0.5: Strip <result> tags if the LLM wrapped the whole thing
    body = re.sub(r'^<result>(.*?)</result>$', r'\1', body.strip(), flags=re.DOTALL)

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
                "value": robust_sanitize_confluence_xhtml(body),
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
    Update a Confluence page. If prepare_confluence_page_merge_update was called first,
    this will merge the new body with the cached existing content. Otherwise, it replaces the page entirely.
    Only allowed if the page is in an allowed space and has 'ai-generated' or 'ai-managed' labels.
    """
    # Check if there's cached content from prepare_confluence_page_merge_update
    cached_data = _prepared_pages_cache.get(page_id)

    if cached_data:
        # Merge workflow: combine cached existing content with new content
        existing_content = cached_data.get("storageContent", "")
        merged_body = existing_content + "\n" + body
        # Clear cache after use
        del _prepared_pages_cache[page_id]
    else:
        # Direct replacement workflow (no prepare step)
        merged_body = body

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
def append_confluence_page(page_id: str, new_content: str) -> Dict[str, Any]:
    """
    Append new content to the bottom of an existing Confluence page.
    Use this instead of update_confluence_page_full when you only want to ADD new sections
    without replacing existing content. Provide ONLY the new section(s) as new_content.
    Only allowed if the page has 'ai-generated' or 'ai-managed' labels.
    """
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
        sanitized_new = robust_sanitize_confluence_xhtml(new_content)
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

        # Return minimal metadata to the agent (NOT the full content)
        return {
            "status": "prepared",
            "page_id": page_id,
            "title": data.get("title"),
            "version": data.get("version", {}).get("number"),
            "message": f"Page {page_id} prepared for update. Content cached server-side. You can now call update_confluence_page_full with your new merged content."
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


