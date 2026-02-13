"""
Phase 0: Foundation Tests
Test current capabilities to establish baseline
"""
import pytest
from src.confluence_mcp.server import search_confluence, get_confluence_page

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

# Add more tests as you understand the codebase
