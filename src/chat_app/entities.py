"""
Entity tracking and resolution for conversational intelligence.

This module provides utilities for extracting and managing entities
(pages, spaces) mentioned in conversations, enabling coreference resolution
("it", "that page", "the same space").
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional


def extract_entities_from_tool_result(
    tool_name: str,
    tool_args: Dict,
    tool_result: str,
    current_entities: Optional[Dict] = None
) -> Dict:
    """Extract entities (pages, spaces) from tool call results.

    Args:
        tool_name: Name of the tool that was called
        tool_args: Arguments passed to the tool
        tool_result: Result returned by the tool
        current_entities: Existing known_entities dict to update

    Returns:
        Updated known_entities dict with newly discovered entities
    """
    if current_entities is None:
        current_entities = {
            "pages": [],
            "spaces": [],
            "last_page": None,
            "last_space": None,
        }

    entities = current_entities.copy()
    timestamp = datetime.now().isoformat()

    # Extract from search_confluence results
    if tool_name == "search_confluence":
        pages = _extract_pages_from_search(tool_result, timestamp)
        entities = _update_pages(entities, pages, timestamp)

        # Extract space from query if present
        if "space" in tool_args:
            space = tool_args["space"]
            entities = _update_space(entities, space)

    # Extract from get_confluence_page results
    elif tool_name == "get_confluence_page":
        page = _extract_page_from_get(tool_args, tool_result, timestamp)
        if page:
            entities = _update_pages(entities, [page], timestamp)

    # Extract from create_confluence_page
    elif tool_name == "create_confluence_page":
        page = _extract_page_from_create(tool_args, tool_result, timestamp)
        if page:
            entities = _update_pages(entities, [page], timestamp)

        # Extract space
        if "spaceKey" in tool_args:
            space = tool_args["spaceKey"]
            entities = _update_space(entities, space)

    # Extract from update_confluence_page_full
    elif tool_name == "update_confluence_page_full":
        # We need the page ID from args
        if "pageId" in tool_args:
            # Try to find this page in existing entities
            page_id = str(tool_args["pageId"])
            existing_page = next((p for p in entities["pages"] if p["id"] == page_id), None)
            if existing_page:
                # Update last_mentioned timestamp
                updated_page = existing_page.copy()
                updated_page["last_mentioned"] = timestamp
                entities = _update_pages(entities, [updated_page], timestamp)

    return entities


def _extract_pages_from_search(result_str: str, timestamp: str) -> List[Dict]:
    """Parse search results to extract page entities."""
    pages = []

    try:
        # Try to parse as JSON
        result_data = json.loads(result_str)

        if isinstance(result_data, dict) and "results" in result_data:
            for item in result_data["results"]:
                page = {
                    "id": str(item.get("id", "")),
                    "title": item.get("title", ""),
                    "space": item.get("space", {}).get("key", ""),
                    "url": item.get("_links", {}).get("webui", ""),
                    "last_mentioned": timestamp,
                }
                if page["id"]:
                    pages.append(page)

    except (json.JSONDecodeError, KeyError, TypeError):
        # Fallback: try to extract from text format
        # Look for patterns like "ID: 12345" or "Title: Something"
        id_matches = re.findall(r'(?:ID|id):\s*(\d+)', result_str)
        title_matches = re.findall(r'(?:Title|title):\s*([^\n]+)', result_str)

        for page_id in id_matches:
            pages.append({
                "id": page_id,
                "title": title_matches[0] if title_matches else f"Page {page_id}",
                "space": "",
                "url": "",
                "last_mentioned": timestamp,
            })

    return pages


def _extract_page_from_get(args: Dict, result_str: str, timestamp: str) -> Optional[Dict]:
    """Extract page entity from get_confluence_page result."""
    page_id = str(args.get("pageId", ""))
    if not page_id:
        return None

    try:
        result_data = json.loads(result_str)
        return {
            "id": page_id,
            "title": result_data.get("title", f"Page {page_id}"),
            "space": result_data.get("space", {}).get("key", ""),
            "url": result_data.get("_links", {}).get("webui", ""),
            "last_mentioned": timestamp,
        }
    except (json.JSONDecodeError, KeyError, TypeError):
        # Fallback: create minimal page entity
        return {
            "id": page_id,
            "title": f"Page {page_id}",
            "space": "",
            "url": "",
            "last_mentioned": timestamp,
        }


def _extract_page_from_create(args: Dict, result_str: str, timestamp: str) -> Optional[Dict]:
    """Extract page entity from create_confluence_page result."""
    try:
        result_data = json.loads(result_str)
        page_id = str(result_data.get("id", ""))

        if not page_id:
            return None

        return {
            "id": page_id,
            "title": args.get("title", result_data.get("title", f"Page {page_id}")),
            "space": args.get("spaceKey", result_data.get("space", {}).get("key", "")),
            "url": result_data.get("_links", {}).get("webui", ""),
            "last_mentioned": timestamp,
        }
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def _update_pages(entities: Dict, new_pages: List[Dict], timestamp: str) -> Dict:
    """Update pages list with new pages, maintaining recency (max 10)."""
    pages = entities.get("pages", []).copy()

    for new_page in new_pages:
        # Remove existing entry if present (will re-add with updated timestamp)
        pages = [p for p in pages if p["id"] != new_page["id"]]
        # Add to front
        pages.insert(0, new_page)

    # Keep only 10 most recent
    pages = pages[:10]

    entities["pages"] = pages

    # Update last_page to the most recent
    if pages:
        entities["last_page"] = pages[0]

    return entities


def _update_space(entities: Dict, space_key: str) -> Dict:
    """Update spaces list and last_space."""
    spaces = entities.get("spaces", []).copy()

    # Add to front if not already present
    if space_key not in spaces:
        spaces.insert(0, space_key)

    # Keep reasonable limit (20 spaces)
    spaces = spaces[:20]

    entities["spaces"] = spaces
    entities["last_space"] = space_key

    return entities


def format_entity_context(entities: Dict) -> str:
    """Format known entities as context string for LLM prompts.

    Args:
        entities: known_entities dict from AgentState

    Returns:
        Formatted string describing known entities
    """
    if not entities:
        return ""

    lines = []

    # Most recent page
    if entities.get("last_page"):
        page = entities["last_page"]
        lines.append(f"Last page mentioned: '{page['title']}' (ID: {page['id']}, Space: {page['space']})")

    # Recent pages (if more than just the last one)
    pages = entities.get("pages", [])
    if len(pages) > 1:
        recent = pages[1:4]  # Show next 3
        page_list = ", ".join([f"'{p['title']}' ({p['id']})" for p in recent])
        lines.append(f"Other recent pages: {page_list}")

    # Last space
    if entities.get("last_space"):
        lines.append(f"Last space mentioned: {entities['last_space']}")

    if lines:
        return "[Entity Context]\n" + "\n".join(lines)
    else:
        return ""


def resolve_coreference(text: str, entities: Dict) -> str:
    """Attempt to resolve coreferences in text (experimental).

    This is a simple rule-based resolver. For production use,
    you'd want a more sophisticated NLP approach.

    Args:
        text: User input text
        entities: known_entities dict

    Returns:
        Text with coreferences resolved (or original if no resolution)
    """
    if not entities:
        return text

    resolved = text

    # Simple patterns for common coreferences
    last_page = entities.get("last_page")
    last_space = entities.get("last_space")

    if last_page:
        # "it" -> page title/ID
        if re.search(r'\bit\b', resolved, re.IGNORECASE):
            resolved = re.sub(
                r'\bit\b',
                f"'{last_page['title']}' (ID: {last_page['id']})",
                resolved,
                count=1,
                flags=re.IGNORECASE
            )

        # "that page" -> page title/ID
        if re.search(r'\bthat page\b', resolved, re.IGNORECASE):
            resolved = re.sub(
                r'\bthat page\b',
                f"page '{last_page['title']}' (ID: {last_page['id']})",
                resolved,
                flags=re.IGNORECASE
            )

        # "the page" -> page title/ID
        if re.search(r'\bthe page\b', resolved, re.IGNORECASE):
            resolved = re.sub(
                r'\bthe page\b',
                f"page '{last_page['title']}' (ID: {last_page['id']})",
                resolved,
                flags=re.IGNORECASE
            )

    if last_space:
        # "that space" -> space key
        if re.search(r'\bthat space\b', resolved, re.IGNORECASE):
            resolved = re.sub(
                r'\bthat space\b',
                f"space {last_space}",
                resolved,
                flags=re.IGNORECASE
            )

        # "the same space" -> space key
        if re.search(r'\bthe same space\b', resolved, re.IGNORECASE):
            resolved = re.sub(
                r'\bthe same space\b',
                f"space {last_space}",
                resolved,
                flags=re.IGNORECASE
            )

    return resolved
