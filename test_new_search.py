import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("CONFLUENCE_BASE_URL", "").rstrip("/")
EMAIL = os.environ.get("CONFLUENCE_EMAIL", "")
API_TOKEN = os.environ.get("CONFLUENCE_API_TOKEN", "")

def load_config():
    cwd_config = os.path.join(os.getcwd(), "config.json")
    if os.path.exists(cwd_config):
        with open(cwd_config, "r") as f:
            return json.load(f)
    return {"allowed_spaces": [], "allowed_parents": {}}

config = load_config()
ALLOWED_SPACES = set(config.get("allowed_spaces", []))
ALLOWED_PARENTS = {k: set(v) for k, v in config.get("allowed_parents", {}).items()}

def get_auth():
    return (EMAIL, API_TOKEN)

def get_headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def search_confluence(query: str):
    """
    Search for Confluence pages using CQL with ancestor filtering.
    """
    # Build base CQL query
    if "=" in query or " IN " in query.upper():
        base_cql = f'({query}) AND type=page'
    else:
        base_cql = f'text~"{query}" AND type=page'
    
    # Build space filter
    if ALLOWED_SPACES:
        space_filter = " OR ".join([f'space = "{s}"' for s in ALLOWED_SPACES])
        base_cql = f'{base_cql} AND ({space_filter})'
    
    # Build ancestor filter for each space
    ancestor_filters = []
    for space_key, parent_ids in ALLOWED_PARENTS.items():
        if parent_ids:
            parent_list = ", ".join(parent_ids)
            space_ancestor_filter = f'(space = "{space_key}" AND (id in ({parent_list}) OR ancestor in ({parent_list})))'
            ancestor_filters.append(space_ancestor_filter)
    
    if ancestor_filters:
        ancestor_cql = " OR ".join(ancestor_filters)
        cql = f'{base_cql} AND ({ancestor_cql})'
    else:
        cql = base_cql
    
    url = f"{BASE_URL}/rest/api/search"
    
    print(f"CQL: {cql}\n")
    
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
        space_key = None
        
        container = result.get("resultGlobalContainer", {})
        display_url = container.get("displayUrl", "")
        if "/spaces/" in display_url:
            parts = display_url.split("/spaces/")
            if len(parts) > 1:
                space_key = parts[1].split("/")[0]
        
        if not space_key:
            web_url = result.get("url", "")
            if "/spaces/" in web_url:
                parts = web_url.split("/spaces/")
                if len(parts) > 1:
                    space_key = parts[1].split("/")[0]
        
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

if __name__ == "__main__":
    print("Config:", json.dumps(config, indent=2))
    print("\n" + "=" * 80)
    print("Testing search for 'docker'")
    print("=" * 80)
    results = search_confluence("docker")
    print(f"\nFound {len(results)} results:")
    for r in results:
        print(f" - {r['title']} (ID: {r['id']})")
        print(f"   URL: {r['url']}")

    print("\n" + "=" * 80)
    print("Testing search for 'google'")
    print("=" * 80)
    results = search_confluence("google")
    print(f"\nFound {len(results)} results:")
    for r in results:
        print(f" - {r['title']} (ID: {r['id']})")
        print(f"   URL: {r['url']}")
