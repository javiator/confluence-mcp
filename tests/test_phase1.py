"""
Phase 1: Multi-Agent Tests
Verify graph structure and tool routing without making real LLM/MCP calls.
"""
import pytest
from confluence_mcp.agent.graph import (
    SEARCH_TOOLS, WRITER_TOOLS, REVIEWER_TOOLS,
    SUPERVISOR_PROMPT, SEARCH_PROMPT, WRITER_PROMPT, REVIEWER_PROMPT,
    AgentState,
)


def test_tool_groups_are_disjoint():
    """Writer and search tools should not overlap (separation of concerns)."""
    overlap = SEARCH_TOOLS & WRITER_TOOLS
    assert not overlap, f"Tool overlap between search and writer: {overlap}"


def test_reviewer_is_subset_of_search():
    """Reviewer only needs read access — a subset of search tools."""
    assert REVIEWER_TOOLS <= SEARCH_TOOLS


def test_all_six_tools_covered():
    """Every MCP tool is assigned to at least one agent."""
    all_tools = SEARCH_TOOLS | WRITER_TOOLS  # reviewer is a subset, no extra tools
    expected = {
        "search_confluence", "get_confluence_page", "get_confluence_children",
        "create_confluence_page", "update_confluence_page_full",
        "prepare_confluence_page_merge_update",
    }
    assert all_tools == expected


def test_supervisor_prompt_has_all_routes():
    """Supervisor prompt must mention all valid routes."""
    for route in ("search", "writer", "reviewer", "end"):
        assert route in SUPERVISOR_PROMPT


def test_agent_prompts_are_concise():
    """Each agent prompt should be under 300 chars to keep token usage low."""
    for name, prompt in [("search", SEARCH_PROMPT), ("writer", WRITER_PROMPT),
                          ("reviewer", REVIEWER_PROMPT)]:
        assert len(prompt) < 300, f"{name} prompt is too long ({len(prompt)} chars)"


def test_agent_state_has_required_keys():
    """AgentState TypedDict must have messages, next, and active_agent."""
    keys = AgentState.__annotations__.keys()
    assert "messages" in keys
    assert "next" in keys
    assert "active_agent" in keys
