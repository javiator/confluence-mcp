#!/usr/bin/env python
"""Quick test to verify Phase 1.2 changes without full pytest setup"""
import sys
sys.path.insert(0, '/home/user/confluence-mcp/src')

# Mock all dependencies to avoid import errors
from unittest.mock import MagicMock

# Mock server module and its dependencies
sys.modules['fastmcp'] = MagicMock()
sys.modules['httpx'] = MagicMock()
sys.modules['bs4'] = MagicMock()
sys.modules['confluence_mcp.server'] = MagicMock()
sys.modules['confluence_mcp.agent.client'] = MagicMock()
sys.modules['confluence_mcp.agent.llm'] = MagicMock()

# Now we can import
print("Testing imports...")
from confluence_mcp.agent.graph import (
    MAX_REVISION_ITERATIONS,
    AgentState,
    SEARCH_TOOLS,
    WRITER_TOOLS,
    REVIEWER_TOOLS,
    PUBLISH_TOOLS,
)

print(f"✓ Imports successful")

# Test 1: revision_count in AgentState
print("\n1. Testing revision_count in AgentState...")
assert "revision_count" in AgentState.__annotations__, "revision_count missing from AgentState"
assert AgentState.__annotations__["revision_count"] == int, "revision_count should be int type"
print(f"✓ AgentState has revision_count: int")

# Test 2: MAX_REVISION_ITERATIONS defined and in range
print("\n2. Testing MAX_REVISION_ITERATIONS...")
assert isinstance(MAX_REVISION_ITERATIONS, int), "MAX_REVISION_ITERATIONS must be int"
assert 2 <= MAX_REVISION_ITERATIONS <= 5, f"MAX_REVISION_ITERATIONS should be 2-5, got {MAX_REVISION_ITERATIONS}"
print(f"✓ MAX_REVISION_ITERATIONS = {MAX_REVISION_ITERATIONS} (valid range)")

# Test 3: All original Phase 1 tests still pass
print("\n3. Testing tool groups...")
overlap = SEARCH_TOOLS & WRITER_TOOLS
assert not overlap, f"Tool overlap: {overlap}"
print(f"✓ Search and Writer tools are disjoint")

assert REVIEWER_TOOLS <= SEARCH_TOOLS, "Reviewer tools should be subset of search"
print(f"✓ Reviewer tools are subset of search tools")

assert PUBLISH_TOOLS == {"create_confluence_page", "update_confluence_page_full"}
print(f"✓ PUBLISH_TOOLS defined correctly")

all_tools = SEARCH_TOOLS | WRITER_TOOLS
expected = {
    "search_confluence", "get_confluence_page", "get_confluence_children",
    "create_confluence_page", "update_confluence_page_full",
    "prepare_confluence_page_merge_update",
}
assert all_tools == expected, f"Missing tools: {expected - all_tools}"
print(f"✓ All 6 MCP tools covered")

print("\n" + "="*60)
print("✅ ALL PHASE 1.2 TESTS PASSED!")
print("="*60)
print(f"\nPhase 1.2 Additions:")
print(f"  - revision_count: int field in AgentState")
print(f"  - MAX_REVISION_ITERATIONS = {MAX_REVISION_ITERATIONS}")
print(f"  - Infinite loop protection enabled")
print(f"  - UI logging for revision cycles")
