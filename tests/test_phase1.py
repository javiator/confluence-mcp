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
    """Each agent prompt should be under 900 chars (quality + token balance)."""
    for name, prompt in [("search", SEARCH_PROMPT), ("writer", WRITER_PROMPT),
                          ("reviewer", REVIEWER_PROMPT)]:
        assert len(prompt) < 900, f"{name} prompt is too long ({len(prompt)} chars)"
        # Still 40%+ shorter than Phase 0's 1500+ char monolith


def test_agent_state_has_required_keys():
    """AgentState TypedDict must have all required keys for review flow."""
    keys = AgentState.__annotations__.keys()
    assert "messages" in keys
    assert "next" in keys
    assert "active_agent" in keys
    assert "pending_tool_call" in keys  # For pre-publish review
    assert "review_status" in keys      # For approval tracking


def test_publish_tools_defined():
    """Publish tools that trigger review must be defined."""
    from confluence_mcp.agent.graph import PUBLISH_TOOLS
    assert PUBLISH_TOOLS == {"create_confluence_page", "update_confluence_page_full"}


def test_reviewer_prompt_has_approval_keywords():
    """Reviewer prompt must instruct on APPROVED/NEEDS REVISION format."""
    assert "APPROVED" in REVIEWER_PROMPT
    assert "NEEDS REVISION" in REVIEWER_PROMPT


def test_writer_prompt_has_critical_rules():
    """Writer prompt must include format, safety, and merge rules."""
    assert "storage format" in WRITER_PROMPT or "XHTML" in WRITER_PROMPT
    assert "ai-generated" in WRITER_PROMPT or "ai-managed" in WRITER_PROMPT
    assert "prepare_confluence_page_merge_update" in WRITER_PROMPT


def test_supervisor_understands_review_flow():
    """Supervisor prompt must understand the review approval cycle."""
    assert "reviewer" in SUPERVISOR_PROMPT.lower()
    assert "approved" in SUPERVISOR_PROMPT.lower() or "approval" in SUPERVISOR_PROMPT.lower()
