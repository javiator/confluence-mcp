"""
Phase 0: Foundation Tests
Test current capabilities to establish baseline
"""
import pytest
from confluence_mcp.server import mcp

def test_environment_setup():
    """Verify environment is set up correctly"""
    import sys
    assert sys.version_info >= (3, 10), "Python 3.10+ required"

def test_imports():
    """Verify all required imports work"""
    try:
        import fastmcp
        import langchain
        import langgraph
        import chainlit
        assert True
    except ImportError as e:
        pytest.fail(f"Missing dependency: {e}")

def test_mcp_server_has_tools():
    """Verify MCP server has expected 6 tools registered"""
    tool_names = list(mcp._tool_manager._tools.keys())
    expected = [
        "search_confluence",
        "get_confluence_page",
        "get_confluence_children",
        "create_confluence_page",
        "update_confluence_page_full",
        "prepare_confluence_page_merge_update",
    ]
    for tool in expected:
        assert tool in tool_names, f"Missing MCP tool: {tool}"

# Add more tests as you understand the codebase
